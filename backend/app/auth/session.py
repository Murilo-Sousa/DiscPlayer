"""Sessão autenticada baseada no cookie assinado do Flask.

O cookie guarda apenas o id do usuário, a chave de sessão da conta e o token de
CSRF (nunca senha, e-mail ou qualquer segredo). Ele é HttpOnly, SameSite=Lax e,
em produção, Secure.

A chave de sessão (`users.session_key`) existe porque o SQLite reaproveita o maior
id depois que uma conta é excluída: sem ela, o cookie de uma conta excluída
passaria a valer para a próxima conta criada. Com ela, o cookie só vale para a
conta exata que o emitiu.
"""
from __future__ import annotations

import hmac
from functools import wraps

from flask import g, session

from ..db import fetch_one
from ..errors import ApiError
from ..security import csrf_token


def current_user() -> dict | None:
    """Usuário autenticado desta requisição (linha completa de `users`) ou None."""
    if "current_user" in g:
        return g.current_user
    user = None
    user_id = session.get("user_id")
    if user_id is not None:
        row = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        user = dict(row) if row else None
        if user is not None and not _same_key(user.get("session_key"), session.get("user_key")):
            user = None  # cookie de outra "geração" desse id (conta excluída e id reaproveitado)
        if user is None:  # conta removida ou cookie inválido: derruba a sessão
            session.pop("user_id", None)
            session.pop("user_key", None)
    g.current_user = user
    return user


def _same_key(stored: str | None, received: object) -> bool:
    if not stored or not isinstance(received, str):
        return False
    return hmac.compare_digest(stored.encode(), received.encode())


def viewer_id() -> int | None:
    """Id do usuário autenticado, ou None para visitantes."""
    user = current_user()
    return user["id"] if user else None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise ApiError(401, "auth_required", "Entre na sua conta para continuar.")
        return view(*args, **kwargs)

    return wrapper


def start_session(user_id: int) -> str:
    """Abre uma sessão nova (descartando a anterior, contra session fixation).

    Devolve o novo token de CSRF, que o front-end deve usar daqui em diante.
    """
    row = fetch_one("SELECT session_key FROM users WHERE id = ?", (user_id,))
    session.clear()
    session["user_id"] = user_id
    session["user_key"] = row["session_key"]
    session.permanent = True
    g.pop("current_user", None)
    return csrf_token()


def end_session() -> str:
    session.clear()
    g.pop("current_user", None)
    return csrf_token()
