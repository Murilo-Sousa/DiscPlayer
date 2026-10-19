"""Sessão autenticada baseada no cookie assinado do Flask.

O cookie guarda apenas o id do usuário e o token de CSRF (nunca senha, e-mail
ou qualquer segredo). Ele é HttpOnly, SameSite=Lax e, em produção, Secure.
"""
from __future__ import annotations

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
        if user is None:  # conta removida: derruba a sessão
            session.pop("user_id", None)
    g.current_user = user
    return user


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
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    g.pop("current_user", None)
    return csrf_token()


def end_session() -> str:
    session.clear()
    g.pop("current_user", None)
    return csrf_token()
