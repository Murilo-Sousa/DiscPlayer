"""Cadastro, login, logout, edição do perfil, foto e exclusão da conta."""
from __future__ import annotations

import secrets
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from ..auth import check_password, current_user, end_session, hash_password, login_required, start_session
from ..db import execute, fetch_one, transaction
from ..errors import ApiError
from ..security import csrf_token, rate_limit
from ..serializers import user_private
from ..services import accounts as accounts_service
from ..services import avatars as avatars_service
from ..utils.dates import utcnow_iso
from ..utils.validation import (
    UNSET,
    FieldErrors,
    json_body,
    read_email,
    read_password,
    read_text,
    read_username,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.get("/me")
def me():
    """Estado da sessão. Também entrega o token de CSRF usado nas próximas requisições."""
    user = current_user()
    return jsonify({"user": user_private(user) if user else None, "csrf_token": csrf_token()})


@bp.post("/register")
@rate_limit("register", 10, 3600)
def register():
    data = json_body()
    errors = FieldErrors()
    username = read_username(data, errors)
    email = read_email(data, errors)
    display_name = read_text(data, "display_name", "Nome de exibição", errors, max_len=50)
    password = read_password(
        data,
        errors,
        username=username if username is not UNSET else None,
        email=email if email is not UNSET else None,
    )
    errors.raise_if_any()
    if display_name in (UNSET, None):
        display_name = username

    password_hash = hash_password(password)  # fora da transação: scrypt é lento de propósito

    taken: dict[str, str] = {}
    try:
        with transaction():
            if fetch_one("SELECT 1 FROM users WHERE username = ?", (username,)):
                taken["username"] = "Este nome de usuário já está em uso."
            if fetch_one("SELECT 1 FROM users WHERE email = ?", (email,)):
                taken["email"] = "Já existe uma conta com este e-mail."
            if not taken:
                cursor = execute(
                    "INSERT INTO users (username, display_name, email, password_hash, session_key, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (username, display_name, email, password_hash, secrets.token_hex(16), utcnow_iso()),
                )
                user_id = cursor.lastrowid
    except sqlite3.IntegrityError:  # duas requisições simultâneas com os mesmos dados
        taken = {"username": "Este nome de usuário ou e-mail já está em uso."}
    if taken:
        raise ApiError(409, "already_exists", "Revise os campos destacados.", fields=taken)

    token = start_session(user_id)
    user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    response = jsonify({"user": user_private(user), "csrf_token": token})
    response.status_code = 201
    return response


@bp.post("/login")
@rate_limit("login", 10, 60)
def login():
    data = json_body()
    identifier, password = data.get("identifier"), data.get("password")
    errors = FieldErrors()
    if not isinstance(identifier, str) or not identifier.strip():
        errors.add("identifier", "Informe seu e-mail ou nome de usuário.")
    if not isinstance(password, str) or not password:
        errors.add("password", "Informe sua senha.")
    errors.raise_if_any()

    key = identifier.strip().lower()
    row = fetch_one("SELECT * FROM users WHERE username = ? OR email = ?", (key, key))
    # A mesma mensagem (e o mesmo tempo) para "usuário inexistente" e "senha errada".
    if not check_password(row["password_hash"] if row else None, password):
        raise ApiError(401, "invalid_credentials", "E-mail, usuário ou senha incorretos.")

    token = start_session(row["id"])
    return jsonify({"user": user_private(row), "csrf_token": token})


@bp.post("/logout")
def logout():
    return jsonify({"user": None, "csrf_token": end_session()})


@bp.patch("/me")
@login_required
def update_me():
    user = current_user()
    data = json_body()
    errors = FieldErrors()
    updates: dict[str, object] = {}

    display_name = read_text(data, "display_name", "Nome de exibição", errors, max_len=50)
    if "display_name" in data:
        if display_name is None:
            errors.add("display_name", "Nome de exibição é obrigatório.")
        elif display_name is not UNSET:
            updates["display_name"] = display_name

    bio = read_text(data, "bio", "A bio", errors, max_len=280, multiline=True)
    if bio is not UNSET:
        updates["bio"] = bio

    # A foto NÃO é editada aqui: `avatar_url` enviado no corpo é ignorado. Ela só muda por
    # POST/DELETE /api/auth/me/avatar, que guardam uma imagem reprocessada pelo servidor.
    errors.raise_if_any()
    if updates:
        # Os nomes das colunas vêm do código acima (lista fechada), nunca do cliente.
        assignments = ", ".join(f"{column} = ?" for column in updates)
        with transaction():
            execute(f"UPDATE users SET {assignments} WHERE id = ?", (*updates.values(), user["id"]))
    row = fetch_one("SELECT * FROM users WHERE id = ?", (user["id"],))
    return jsonify({"user": user_private(row)})


@bp.post("/me/avatar")
@login_required
@rate_limit("avatar", 20, 3600)
def upload_avatar():
    """Envia a foto do perfil (multipart/form-data, campo `file`; JPG, PNG ou WebP)."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ApiError(
            422, "validation_error", "Revise a foto escolhida.", fields={"file": "Escolha uma imagem para enviar."}
        )
    limit = current_app.config["AVATAR_MAX_UPLOAD_BYTES"]
    raw = upload.stream.read(limit + 1)
    if len(raw) > limit:
        raise ApiError(413, "payload_too_large", "A foto é grande demais. Envie um arquivo de até 5 MB.")
    avatars_service.set_avatar(current_user()["id"], raw)
    return jsonify({"user": user_private(fetch_one("SELECT * FROM users WHERE id = ?", (current_user()["id"],)))})


@bp.delete("/me/avatar")
@login_required
def delete_avatar():
    avatars_service.remove_avatar(current_user()["id"])
    return jsonify({"user": user_private(fetch_one("SELECT * FROM users WHERE id = ?", (current_user()["id"],)))})


@bp.delete("/me")
@login_required
@rate_limit("delete-account", 5, 3600)
def delete_account():
    """Exclui a conta e todos os dados dela. Pede a senha de novo: um cookie roubado não basta."""
    user = current_user()
    data = json_body()
    password = data.get("password")
    if not isinstance(password, str) or not password:
        raise ApiError(422, "validation_error", "Revise os campos destacados.", fields={"password": "Informe sua senha."})
    if not check_password(user["password_hash"], password):
        raise ApiError(403, "invalid_password", "Senha incorreta.", fields={"password": "Senha incorreta."})
    accounts_service.delete_account(user["id"])
    return jsonify({"user": None, "csrf_token": end_session()})
