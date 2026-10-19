"""Atividades: feed de quem o usuário segue, atividade de um perfil e atividade global."""
from __future__ import annotations

import sqlite3

from ..db import fetch_all

ACTIVITY_SELECT = """
SELECT a.id AS activity_id, a.type, a.status AS activity_status, a.created_at AS activity_created_at,
       u.username, u.display_name, u.avatar_url,
       g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,
       r.id AS review_id, r.rating AS review_rating, r.body AS review_body,
       (SELECT COUNT(*) FROM review_likes rl WHERE rl.review_id = r.id) AS review_like_count,
       l.id AS list_id, l.title AS list_title
  FROM activities a
  JOIN users u ON u.id = a.user_id
  LEFT JOIN games g ON g.id = a.game_id
  LEFT JOIN reviews r ON r.id = a.review_id
  LEFT JOIN lists l ON l.id = a.list_id
"""

# Atividades de listas só aparecem se a lista for pública (ou se quem vê for o dono).
VISIBILITY = "(a.type <> 'list_created' OR l.is_public = 1 OR a.user_id = :viewer)"

_SCOPES = {
    "global": "1 = 1",
    "user": "a.user_id = :target",
    "following": "a.user_id IN (SELECT followed_id FROM follows WHERE follower_id = :viewer)",
}


def activities(
    scope: str,
    *,
    viewer_id: int | None = None,
    target_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """`scope` é uma de: global, user (perfil de target_id), following (quem viewer_id segue)."""
    return fetch_all(
        f"{ACTIVITY_SELECT} WHERE {_SCOPES[scope]} AND {VISIBILITY}"
        " ORDER BY a.created_at DESC, a.id DESC LIMIT :limit OFFSET :offset",
        {"viewer": viewer_id, "target": target_id, "limit": limit, "offset": offset},
    )
