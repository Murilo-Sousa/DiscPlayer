"""Pesquisa local (usuários, listas públicas e reviews). Os jogos vêm da RAWG."""
from __future__ import annotations

import sqlite3

from ..db import fetch_all
from ..utils.text import escape_like
from . import lists as lists_service
from . import reviews as reviews_service


def users(term: str, limit: int = 5) -> list[sqlite3.Row]:
    pattern = f"%{escape_like(term.lower())}%"
    return fetch_all(
        "SELECT username, display_name, avatar_url, bio, is_demo FROM users"
        " WHERE lower(username) LIKE :p ESCAPE '\\' OR lower(display_name) LIKE :p ESCAPE '\\'"
        " ORDER BY (username = :exact) DESC, (username LIKE :prefix ESCAPE '\\') DESC, username LIMIT :limit",
        {"p": pattern, "exact": term.lower(), "prefix": f"{escape_like(term.lower())}%", "limit": limit},
    )


def lists(term: str, limit: int = 5) -> list[sqlite3.Row]:
    return lists_service.community_lists(query=term, limit=limit)


def reviews(term: str, viewer_id: int | None, limit: int = 5) -> list[sqlite3.Row]:
    pattern = f"%{escape_like(term)}%"
    return fetch_all(
        f"SELECT {reviews_service.REVIEW_COLUMNS} {reviews_service.REVIEW_FROM}"
        " WHERE r.body LIKE :p ESCAPE '\\' AND r.has_spoilers = 0 ORDER BY r.created_at DESC, r.id DESC LIMIT :limit",
        {"p": pattern, "viewer": viewer_id, "limit": limit},
    )
