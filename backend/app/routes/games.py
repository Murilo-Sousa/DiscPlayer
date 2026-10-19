"""Catálogo (RAWG) e página do jogo (RAWG + dados da comunidade DiscPlayer)."""
from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from ..auth import viewer_id
from ..db import fetch_all
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import entry_from_row, game_from_local, game_from_row, review_from_row
from ..services import games as games_service
from ..services import lists as lists_service
from ..services import library as library_service
from ..services import rawg, reviews as reviews_service
from ..utils.dates import today_utc
from ..utils.pagination import page_envelope, page_args

bp = Blueprint("games", __name__, url_prefix="/api")

_SLUG_LIST = re.compile(r"^[a-z0-9-]+(,[a-z0-9-]+){0,4}$")
_ID_LIST = re.compile(r"^\d+(,\d+){0,4}$")


def _bad(name: str, message: str):
    raise ApiError(400, "invalid_parameter", f"Parâmetro '{name}' inválido: {message}")


def _catalog_params() -> dict:
    args = request.args
    q = (args.get("q") or "").strip()
    if len(q) > 100:
        _bad("q", "use até 100 caracteres.")
    genre = (args.get("genre") or "").strip().lower()
    if genre and not _SLUG_LIST.match(genre):
        _bad("genre", "informe o identificador (slug) do gênero.")
    platform = (args.get("platform") or "").strip()
    if platform and not _ID_LIST.match(platform):
        _bad("platform", "informe o número da plataforma.")
    year = None
    if args.get("year"):
        try:
            year = int(args["year"])
        except ValueError:
            _bad("year", "informe um ano com 4 dígitos.")
        if not 1970 <= year <= today_utc().year + 2:
            _bad("year", f"use um ano entre 1970 e {today_utc().year + 2}.")
    ordering = (args.get("ordering") or "relevance").strip()
    if ordering not in rawg.ORDERINGS:
        _bad("ordering", "use um de: " + ", ".join(rawg.ORDERINGS) + ".")
    if ordering == "relevance" and not q:
        ordering = "popular"  # sem texto de busca não existe "relevância"
    page, page_size = page_args(default_per_page=24, max_per_page=40)
    return {
        "search": q or None,
        "page": page,
        "page_size": page_size,
        "genres": genre or None,
        "platforms": platform or None,
        "year": year,
        "ordering": ordering,
    }


@bp.get("/games")
@rate_limit("catalog", 120, 60)
def catalog():
    params = _catalog_params()
    data = rawg.search_games(**params)
    data["ordering"] = params["ordering"]
    return jsonify(data)


@bp.get("/games/featured")
@rate_limit("catalog", 120, 60)
def featured():
    """Popular e lançamentos recentes para a página inicial. Falhas parciais não derrubam a outra lista."""
    out: dict = {"popular": None, "new": None, "errors": {}}
    for kind in ("popular", "new"):
        try:
            out[kind] = rawg.featured_games(kind)["results"]
        except rawg.RawgError as exc:
            out["errors"][kind] = {"code": exc.code, "message": exc.message}
            out[kind] = []
    if len(out["errors"]) == 2:
        first = next(iter(out["errors"].values()))
        raise ApiError(503, first["code"], first["message"])
    return jsonify(out)


@bp.get("/games/top-rated")
def top_rated():
    """Jogos mais bem avaliados pela comunidade DiscPlayer (média das reviews reais)."""
    _, per_page = page_args(default_per_page=8, max_per_page=20)
    rows = fetch_all(
        "SELECT g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,"
        " AVG(r.rating) AS average, COUNT(*) AS count FROM reviews r JOIN games g ON g.id = r.game_id"
        " GROUP BY g.id ORDER BY average DESC, count DESC, g.name LIMIT ?",
        (per_page,),
    )
    return jsonify(
        {"items": [{"game": game_from_row(r), "average": round(r["average"], 2), "count": r["count"]} for r in rows]}
    )


@bp.get("/genres")
def genres():
    return jsonify({"items": rawg.list_genres()})


@bp.get("/platforms")
def platforms():
    return jsonify({"items": rawg.list_platforms()})


def _community_block(local: dict | None) -> dict:
    """Bloco da comunidade DiscPlayer: sempre separado das notas da RAWG."""
    if local is None:
        return {
            "average": None,
            "count": 0,
            "with_text": 0,
            "distribution": [0] * 10,
            "library": {"total": 0, "quero_jogar": 0, "jogando": 0, "zerado": 0, "abandonado": 0, "pausado": 0},
        }
    return reviews_service.community_stats(local["id"])


@bp.get("/games/<int:rawg_id>")
@rate_limit("game-detail", 120, 60)
def game_detail(rawg_id: int):
    local = games_service.get_local_game(rawg_id)
    notice = None
    try:
        detail = rawg.get_game(rawg_id)
        detail["screenshots"] = rawg.get_screenshots(rawg_id)
        detail["source"] = "rawg"
        if local and (local["name"], local["cover_url"]) != (detail["name"], detail.get("cover_url")):
            local = games_service.sync_game(detail)  # mantém a cópia local em dia
    except rawg.RawgNotFound:
        raise
    except rawg.RawgError as exc:
        if local is None:
            raise
        # A RAWG falhou, mas o jogo já está no banco: servimos o que existe localmente.
        base = game_from_local(local)
        detail = {
            **base,
            "genres": [],
            "platforms": [],
            "developers": [],
            "publishers": [],
            "description": "",
            "screenshots": [],
            "cover_additional_url": None,
            "website": None,
            "esrb": None,
            "playtime": None,
            "metacritic": None,
            "rawg_rating": None,
            "rawg_ratings_count": 0,
            "source": "local",
        }
        notice = {"code": exc.code, "message": exc.message}

    uid = viewer_id()
    payload: dict = {"game": detail, "community": _community_block(local), "notice": notice, "viewer": None}
    if local:
        payload["reviews"] = [
            review_from_row(r, with_game=False)
            for r in reviews_service.list_for_game(local["id"], uid, limit=5)
        ]
    else:
        payload["reviews"] = []
    if uid is not None:
        entry = library_service.get_entry(uid, local["id"]) if local else None
        mine = reviews_service.get_user_review(uid, local["id"], uid) if local else None
        payload["viewer"] = {
            "entry": entry_from_row(entry) if entry else None,
            "review": review_from_row(mine, with_game=False, with_user=False) if mine else None,
            "list_ids": sorted(lists_service.membership(uid, rawg_id)),
        }
    return jsonify(payload)


@bp.get("/games/<int:rawg_id>/reviews")
def game_reviews(rawg_id: int):
    local = games_service.get_local_game(rawg_id)
    page, per_page = page_args(default_per_page=10, max_per_page=30)
    sort = request.args.get("sort", "recent")
    if sort not in {"recent", "popular", "highest", "lowest"}:
        _bad("sort", "use recent, popular, highest ou lowest.")
    if local is None:
        return jsonify(page_envelope([], page, per_page))
    rows = reviews_service.list_for_game(
        local["id"], viewer_id(), sort=sort, limit=per_page + 1, offset=(page - 1) * per_page
    )
    return jsonify(page_envelope(rows, page, per_page, [review_from_row(r, with_game=False) for r in rows[:per_page]]))
