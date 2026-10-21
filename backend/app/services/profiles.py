"""Perfis públicos, estatísticas calculadas e relações de seguir."""
from __future__ import annotations

import sqlite3

from ..db import execute, fetch_all, fetch_one, transaction
from ..errors import ApiError
from ..utils.dates import today_utc, utcnow_iso


def get_by_username(username: str) -> sqlite3.Row | None:
    return fetch_one(
        "SELECT id, username, display_name, bio, avatar_url, created_at FROM users WHERE username = ?",
        (username.strip().lower(),),
    )


def _distribution(user_id: int) -> list[int]:
    buckets = [0] * 10
    for row in fetch_all(
        "SELECT MIN(CAST(rating AS INTEGER), 9) AS bucket, COUNT(*) AS n"
        " FROM reviews WHERE user_id = ? GROUP BY bucket",
        (user_id,),
    ):
        buckets[row["bucket"]] = row["n"]
    return buckets


def completions_by_month(user_id: int, year: int) -> list[int]:
    """Zeradas em cada mês do ano (índice 0 = janeiro), pela data de término.

    Conta a jogada atual e as jogadas anteriores: zerar o mesmo jogo duas vezes
    no ano conta duas vezes, e recomeçar um jogo não apaga a conclusão anterior.
    """
    counts = [0] * 12
    for row in fetch_all(
        "SELECT CAST(substr(completed_at, 6, 2) AS INTEGER) AS month, COUNT(*) AS n FROM ("
        " SELECT completed_at FROM library_entries"
        "  WHERE user_id = :u AND status = 'zerado' AND completed_at BETWEEN :a AND :b"
        " UNION ALL"
        " SELECT completed_at FROM playthroughs"
        "  WHERE user_id = :u AND status = 'zerado' AND completed_at BETWEEN :a AND :b"
        ") GROUP BY month",
        {"u": user_id, "a": f"{year}-01-01", "b": f"{year}-12-31"},
    ):
        if 1 <= row["month"] <= 12:
            counts[row["month"] - 1] = row["n"]
    return counts


def list_follows(user_id: int, direction: str, *, limit: int = 30, offset: int = 0) -> list[sqlite3.Row]:
    """Seguidores ('followers') ou seguidos ('following') de um usuário, do mais recente ao mais antigo."""
    if direction == "followers":
        join, where = "f.follower_id", "f.followed_id"
    elif direction == "following":
        join, where = "f.followed_id", "f.follower_id"
    else:
        raise ValueError(direction)
    return fetch_all(
        f"SELECT u.username, u.display_name, u.avatar_url, u.bio FROM follows f"
        f" JOIN users u ON u.id = {join} WHERE {where} = ?"
        " ORDER BY f.created_at DESC, f.id DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )


def stats_for(user_id: int, *, include_private_lists: bool) -> dict:
    """Todas as estatísticas saem de consultas aos registros reais do usuário."""
    year = today_utc().year
    year_start = f"{year}-01-01"
    library = fetch_one(
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(status = 'quero_jogar'), 0) AS quero_jogar,"
        " COALESCE(SUM(status = 'jogando'), 0) AS jogando,"
        " COALESCE(SUM(status = 'zerado'), 0) AS zerado,"
        " COALESCE(SUM(status = 'abandonado'), 0) AS abandonado,"
        " COALESCE(SUM(status = 'pausado'), 0) AS pausado,"
        " COALESCE(SUM(is_favorite), 0) AS favorites,"
        " COALESCE(SUM(status = 'zerado' AND completed_at >= ?), 0) AS completed_this_year"
        " FROM library_entries WHERE user_id = ?",
        (year_start, user_id),
    )
    past_completions = fetch_one(
        "SELECT COUNT(*) AS n FROM playthroughs"
        " WHERE user_id = ? AND status = 'zerado' AND completed_at >= ?",
        (user_id, year_start),
    )["n"]
    reviews = fetch_one(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg, COALESCE(SUM(body IS NOT NULL), 0) AS with_text"
        " FROM reviews WHERE user_id = ?",
        (user_id,),
    )
    lists = fetch_one(
        "SELECT COUNT(*) AS n FROM lists WHERE user_id = ?" + ("" if include_private_lists else " AND is_public = 1"),
        (user_id,),
    )
    follows = fetch_one(
        "SELECT (SELECT COUNT(*) FROM follows WHERE followed_id = ?) AS followers,"
        " (SELECT COUNT(*) FROM follows WHERE follower_id = ?) AS following",
        (user_id, user_id),
    )
    return {
        "games": library["total"],
        "by_status": {
            key: library[key] for key in ("quero_jogar", "jogando", "zerado", "abandonado", "pausado")
        },
        "completed_this_year": library["completed_this_year"] + past_completions,
        "completions_by_month": completions_by_month(user_id, year),
        "favorites": library["favorites"],
        "ratings": reviews["n"],
        "reviews_with_text": reviews["with_text"],
        "average_rating": round(reviews["avg"], 2) if reviews["avg"] is not None else None,
        "rating_distribution": _distribution(user_id),
        "lists": lists["n"],
        "followers": follows["followers"],
        "following": follows["following"],
    }


def is_following(follower_id: int | None, followed_id: int) -> bool:
    if follower_id is None:
        return False
    return fetch_one(
        "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?", (follower_id, followed_id)
    ) is not None


def set_follow(follower_id: int, followed_id: int, follow: bool) -> int:
    """Segue/deixa de seguir (idempotente). Devolve o total de seguidores do alvo."""
    if follower_id == followed_id:
        raise ApiError(400, "cannot_follow_self", "Você não pode seguir a si mesmo.")
    with transaction():
        if follow:
            execute(
                "INSERT OR IGNORE INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                (follower_id, followed_id, utcnow_iso()),
            )
        else:
            execute(
                "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?", (follower_id, followed_id)
            )
        return fetch_one("SELECT COUNT(*) AS n FROM follows WHERE followed_id = ?", (followed_id,))["n"]
