"""Reviews (nota + texto opcional), médias da comunidade e curtidas."""
from __future__ import annotations

import sqlite3

from ..db import execute, fetch_all, fetch_one, transaction
from ..errors import ApiError
from ..utils.dates import utcnow_iso
from . import library

KEEP = object()  # "não mexer neste campo" (None é um valor válido: limpa o texto)

REVIEW_COLUMNS = """
    r.id AS review_id, r.rating, r.body, r.has_spoilers,
    r.created_at AS review_created_at, r.updated_at AS review_updated_at,
    u.username, u.display_name, u.avatar_url, u.is_demo,
    g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,
    (SELECT COUNT(*) FROM review_likes rl WHERE rl.review_id = r.id) AS like_count,
    EXISTS (SELECT 1 FROM review_likes rl
             WHERE rl.review_id = r.id AND rl.user_id = :viewer) AS liked
"""
REVIEW_FROM = "FROM reviews r JOIN users u ON u.id = r.user_id JOIN games g ON g.id = r.game_id"

_SORTS = {
    "recent": "r.created_at DESC, r.id DESC",
    "popular": "like_count DESC, r.created_at DESC, r.id DESC",
    "highest": "r.rating DESC, r.created_at DESC",
    "lowest": "r.rating ASC, r.created_at DESC",
}


def get_review(review_id: int, viewer_id: int | None) -> sqlite3.Row | None:
    return fetch_one(
        f"SELECT {REVIEW_COLUMNS} {REVIEW_FROM} WHERE r.id = :id",
        {"id": review_id, "viewer": viewer_id},
    )


def get_user_review(user_id: int, game_id: int, viewer_id: int | None) -> sqlite3.Row | None:
    return fetch_one(
        f"SELECT {REVIEW_COLUMNS} {REVIEW_FROM} WHERE r.user_id = :uid AND r.game_id = :gid",
        {"uid": user_id, "gid": game_id, "viewer": viewer_id},
    )


def list_for_game(
    game_id: int,
    viewer_id: int | None,
    *,
    sort: str = "recent",
    only_text: bool = True,
    limit: int = 10,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where = "r.game_id = :gid" + (" AND r.body IS NOT NULL" if only_text else "")
    return fetch_all(
        f"SELECT {REVIEW_COLUMNS} {REVIEW_FROM} WHERE {where}"
        f" ORDER BY {_SORTS.get(sort, _SORTS['recent'])} LIMIT :limit OFFSET :offset",
        {"gid": game_id, "viewer": viewer_id, "limit": limit, "offset": offset},
    )


def list_for_user(
    user_id: int, viewer_id: int | None, *, only_text: bool = False, limit: int = 20, offset: int = 0
) -> list[sqlite3.Row]:
    where = "r.user_id = :uid" + (" AND r.body IS NOT NULL" if only_text else "")
    return fetch_all(
        f"SELECT {REVIEW_COLUMNS} {REVIEW_FROM} WHERE {where}"
        " ORDER BY r.created_at DESC, r.id DESC LIMIT :limit OFFSET :offset",
        {"uid": user_id, "viewer": viewer_id, "limit": limit, "offset": offset},
    )


def list_recent(viewer_id: int | None, *, limit: int = 10, offset: int = 0) -> list[sqlite3.Row]:
    """Reviews com texto publicadas mais recentemente na comunidade."""
    return fetch_all(
        f"SELECT {REVIEW_COLUMNS} {REVIEW_FROM} WHERE r.body IS NOT NULL"
        " ORDER BY r.created_at DESC, r.id DESC LIMIT :limit OFFSET :offset",
        {"viewer": viewer_id, "limit": limit, "offset": offset},
    )


def get_author_id(review_id: int) -> int | None:
    row = fetch_one("SELECT user_id FROM reviews WHERE id = ?", (review_id,))
    return row["user_id"] if row else None


def create_review(
    user_id: int, game: dict, rating: float, body: str | None, has_spoilers: bool = False, *, today: str | None = None
) -> int:
    """Publica a nota (e o texto). Só quem já começou o jogo avalia: veja `library.require_can_rate`."""
    now = utcnow_iso()
    game_id = game["id"]
    with transaction():
        library.require_can_rate(user_id, game, today)  # dentro da transação: o status não muda entre a checagem e o INSERT
        if fetch_one("SELECT 1 FROM reviews WHERE user_id = ? AND game_id = ?", (user_id, game_id)):
            raise ApiError(
                409,
                "review_exists",
                "Você já avaliou este jogo. Edite a sua avaliação em vez de criar outra.",
            )
        cursor = execute(
            "INSERT INTO reviews (user_id, game_id, rating, body, has_spoilers, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, game_id, rating, body, _spoiler_flag(body, has_spoilers), now),
        )
        review_id = cursor.lastrowid
        execute(
            "INSERT INTO activities (user_id, type, game_id, review_id, created_at)"
            " VALUES (?, 'reviewed', ?, ?, ?)",
            (user_id, game_id, review_id, now),
        )
    return review_id  # type: ignore[return-value]


def _spoiler_flag(body: str | None, has_spoilers: bool) -> int:
    """O aviso só faz sentido para quem tem texto: sem texto, nunca fica marcado."""
    return int(bool(has_spoilers) and body is not None)


def update_review(review_id: int, *, rating=None, body=KEEP, has_spoilers=KEEP) -> None:
    """Atualiza nota, texto e/ou aviso de spoilers. `updated_at` marca a edição (nulo até a primeira)."""
    with transaction():
        current = fetch_one("SELECT body, has_spoilers FROM reviews WHERE id = ?", (review_id,))
        new_body = current["body"] if body is KEEP else body
        new_flag = bool(current["has_spoilers"]) if has_spoilers is KEEP else has_spoilers
        sets, params = ["updated_at = ?", "body = ?", "has_spoilers = ?"], [
            utcnow_iso(),
            new_body,
            _spoiler_flag(new_body, new_flag),
        ]
        if rating is not None:
            sets.append("rating = ?")
            params.append(rating)
        execute(f"UPDATE reviews SET {', '.join(sets)} WHERE id = ?", (*params, review_id))


def delete_review(review_id: int) -> None:
    with transaction():
        execute("DELETE FROM reviews WHERE id = ?", (review_id,))  # curtidas e atividade saem em cascata


def community_stats(game_id: int) -> dict:
    """Média e distribuição calculadas a partir das reviews reais do banco."""
    summary = fetch_one(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg, SUM(body IS NOT NULL) AS with_text"
        " FROM reviews WHERE game_id = ?",
        (game_id,),
    )
    buckets = [0] * 10  # [0–1), [1–2) ... [9–10]; a nota 10 conta na última faixa
    for row in fetch_all(
        "SELECT MIN(CAST(rating AS INTEGER), 9) AS bucket, COUNT(*) AS n"
        " FROM reviews WHERE game_id = ? GROUP BY bucket",
        (game_id,),
    ):
        buckets[row["bucket"]] = row["n"]
    library = {"total": 0, "quero_jogar": 0, "jogando": 0, "zerado": 0, "abandonado": 0, "pausado": 0}
    for row in fetch_all(
        "SELECT status, COUNT(*) AS n FROM library_entries WHERE game_id = ? GROUP BY status", (game_id,)
    ):
        library[row["status"]] = row["n"]
        library["total"] += row["n"]
    return {
        "average": round(summary["avg"], 2) if summary["avg"] is not None else None,
        "count": summary["n"],
        "with_text": summary["with_text"] or 0,
        "distribution": buckets,
        "library": library,
    }


def set_like(user_id: int, review_id: int, liked: bool) -> int:
    """Curte ou descurte (idempotente). Devolve o total de curtidas."""
    with transaction():
        if not fetch_one("SELECT 1 FROM reviews WHERE id = ?", (review_id,)):
            raise ApiError(404, "not_found", "Review não encontrada.")
        if liked:
            # UNIQUE (user_id, review_id) + OR IGNORE: curtir duas vezes não duplica.
            execute(
                "INSERT OR IGNORE INTO review_likes (user_id, review_id, created_at) VALUES (?, ?, ?)",
                (user_id, review_id, utcnow_iso()),
            )
        else:
            execute("DELETE FROM review_likes WHERE user_id = ? AND review_id = ?", (user_id, review_id))
        return fetch_one("SELECT COUNT(*) AS n FROM review_likes WHERE review_id = ?", (review_id,))["n"]
