"""Imagens de compartilhamento: o que aparece quando um link do site é colado em outro app.

São PNGs de 1200 x 630 desenhados no servidor (veja `services/cards.py`) só com dados públicos.
Ficam em cache por alguns minutos, e a chave do cache inclui os próprios dados desenhados, então
uma mudança no perfil aparece na imagem sem esperar o cache vencer.
"""
from __future__ import annotations

import hashlib
import json

from flask import Blueprint, Response

from ..errors import ApiError
from ..security import rate_limit
from ..services import avatars as avatars_service
from ..services import cards
from ..services import profiles as profiles_service
from ..services import retrospective as retrospective_service
from ..utils.cache import TTLCache

bp = Blueprint("share", __name__, url_prefix="/api/share")

_cache = TTLCache(max_entries=200)
CACHE_SECONDS = 600


def _fingerprint(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def _png(key: tuple, render) -> Response:
    data = _cache.get(key)
    if data is None:
        data = render()
        _cache.set(key, data, ttl=CACHE_SECONDS)
    response = Response(data, mimetype="image/png")
    response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return response


def _user(username: str):
    user = profiles_service.get_by_username(username)
    if user is None:
        raise ApiError(404, "not_found", "Jogador não encontrado.")
    return user


@bp.get("/default.png")
@rate_limit("share-card", 120, 60)
def default_card():
    return _png(("default",), cards.default_card)


@bp.get("/profile/<username>.png")
@rate_limit("share-card", 120, 60)
def profile_card(username: str):
    user = _user(username)
    stats = profiles_service.stats_for(user["id"], include_private_lists=False)
    avatar = avatars_service.data_for_user(user["id"])
    drawn = {
        "name": user["display_name"],
        "username": user["username"],
        "bio": user["bio"],
        "games": stats["games"],
        "zerado": stats["by_status"]["zerado"],
        "average": stats["average_rating"],
    }
    key = ("profile", _fingerprint(drawn, hashlib.sha256(avatar).hexdigest() if avatar else None))
    return _png(
        key,
        lambda: cards.profile_card(
            display_name=user["display_name"],
            username=user["username"],
            bio=user["bio"],
            stats=stats,
            avatar_bytes=avatar,
        ),
    )


@bp.get("/retrospective/<username>/<int:year>.png")
@rate_limit("share-card", 120, 60)
def retrospective_card(username: str, year: int):
    user = _user(username)
    retrospective_service.require_valid_year(year)
    data = retrospective_service.build(user, year)
    if data["empty"]:
        raise ApiError(404, "not_found", "Não há registros neste ano.")
    key = ("retrospective", _fingerprint(data))
    return _png(key, lambda: cards.retrospective_card(data))
