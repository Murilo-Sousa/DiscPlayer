"""Pesquisa global: jogos (RAWG), jogadores, listas públicas e reviews.

Se a RAWG falhar, os resultados locais continuam sendo entregues e o erro dos
jogos vai em `games.error`.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..auth import viewer_id
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import EXCERPT_LENGTH, review_from_row, user_public
from ..services import rawg
from ..services import search as search_service
from .lists import summaries

bp = Blueprint("search", __name__, url_prefix="/api")

MIN_LENGTH = 2
MAX_LENGTH = 100


def _review_hit(row) -> dict:
    data = review_from_row(row)
    body = data.pop("body") or ""
    data["excerpt"] = body[:EXCERPT_LENGTH].rstrip() + ("…" if len(body) > EXCERPT_LENGTH else "")
    return data


@bp.get("/search")
@rate_limit("search", 90, 60)
def search():
    term = " ".join((request.args.get("q") or "").split())
    if len(term) < MIN_LENGTH:
        raise ApiError(400, "invalid_parameter", f"Digite pelo menos {MIN_LENGTH} caracteres para pesquisar.")
    if len(term) > MAX_LENGTH:
        raise ApiError(400, "invalid_parameter", f"Use até {MAX_LENGTH} caracteres na pesquisa.")

    games: dict = {"items": [], "error": None}
    try:
        games["items"] = rawg.search_games(search=term, page_size=6)["results"]
    except rawg.RawgError as exc:
        games["error"] = {"code": exc.code, "message": exc.message}

    return jsonify(
        {
            "query": term,
            "games": games,
            "users": [user_public(r) for r in search_service.users(term)],
            "lists": summaries(search_service.lists(term)),
            "reviews": [_review_hit(r) for r in search_service.reviews(term, viewer_id())],
        }
    )
