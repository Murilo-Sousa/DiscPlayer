"""Listas personalizadas de jogos."""
from __future__ import annotations

import sqlite3

from ..db import execute, fetch_all, fetch_one, transaction
from ..errors import ApiError
from ..serializers import game_out
from ..utils.dates import utcnow_iso
from ..utils.text import escape_like

MAX_LISTS_PER_USER = 100
MAX_GAMES_PER_LIST = 200

LIST_COLUMNS = """
    l.id, l.title, l.description, l.is_public, l.created_at, l.updated_at,
    l.user_id AS owner_id, u.username, u.display_name, u.avatar_url,
    (SELECT COUNT(*) FROM list_games lg WHERE lg.list_id = l.id) AS game_count
"""
LIST_FROM = "FROM lists l JOIN users u ON u.id = l.user_id"


def covers_for(list_ids: list[int], per_list: int = 4) -> dict[int, list[dict]]:
    """Primeiras capas de cada lista (para a composição visual da lista)."""
    if not list_ids:
        return {}
    marks = ",".join("?" * len(list_ids))
    rows = fetch_all(
        f"SELECT lg.list_id, g.rawg_id, g.name, g.slug, g.cover_url FROM list_games lg"
        f" JOIN games g ON g.id = lg.game_id WHERE lg.list_id IN ({marks}) AND g.cover_url IS NOT NULL"
        " ORDER BY lg.list_id, lg.position, lg.id",
        tuple(list_ids),
    )
    covers: dict[int, list[dict]] = {i: [] for i in list_ids}
    for row in rows:
        if len(covers[row["list_id"]]) < per_list:
            game = game_out(row["rawg_id"], row["name"], row["slug"], row["cover_url"])
            covers[row["list_id"]].append(
                {"name": game["name"], "cover_url": game["cover_url"], "cover_thumb_url": game["cover_thumb_url"]}
            )
    return covers


def get_visible(list_id: int, viewer_id: int | None) -> sqlite3.Row | None:
    """A lista, se o visitante puder vê-la. Privada de outro usuário = inexistente."""
    row = fetch_one(f"SELECT {LIST_COLUMNS} {LIST_FROM} WHERE l.id = ?", (list_id,))
    if row is None or (not row["is_public"] and row["owner_id"] != viewer_id):
        return None
    return row


def get_owned(list_id: int, user_id: int) -> sqlite3.Row:
    """A lista, exigindo que pertença ao usuário (404 se não existir ou for privada alheia, 403 se for pública alheia)."""
    row = get_visible(list_id, user_id)
    if row is None:
        raise ApiError(404, "not_found", "Lista não encontrada.")
    if row["owner_id"] != user_id:
        raise ApiError(403, "forbidden", "Você só pode alterar as suas próprias listas.")
    return row


def list_items(list_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT lg.position, lg.added_at, g.rawg_id, g.name AS game_name, g.slug AS game_slug,"
        " g.cover_url, g.release_date FROM list_games lg JOIN games g ON g.id = lg.game_id"
        " WHERE lg.list_id = ? ORDER BY lg.position, lg.id",
        (list_id,),
    )


def community_lists(*, query: str | None = None, limit: int = 12, offset: int = 0) -> list[sqlite3.Row]:
    where, params = ["l.is_public = 1", "(SELECT COUNT(*) FROM list_games x WHERE x.list_id = l.id) > 0"], []
    if query:
        where.append("l.title LIKE ? ESCAPE '\\'")
        params.append(f"%{escape_like(query)}%")
    return fetch_all(
        f"SELECT {LIST_COLUMNS} {LIST_FROM} WHERE {' AND '.join(where)}"
        " ORDER BY l.updated_at DESC, l.id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )


def lists_of_user(
    user_id: int, *, include_private: bool, limit: int = 50, offset: int = 0
) -> list[sqlite3.Row]:
    visibility = "" if include_private else " AND l.is_public = 1"
    return fetch_all(
        f"SELECT {LIST_COLUMNS} {LIST_FROM} WHERE l.user_id = ?{visibility}"
        " ORDER BY l.updated_at DESC, l.id DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )


def membership(user_id: int, rawg_id: int) -> set[int]:
    """Ids das listas do usuário que já contêm o jogo."""
    return {
        row["list_id"]
        for row in fetch_all(
            "SELECT lg.list_id FROM list_games lg JOIN lists l ON l.id = lg.list_id"
            " JOIN games g ON g.id = lg.game_id WHERE l.user_id = ? AND g.rawg_id = ?",
            (user_id, rawg_id),
        )
    }


def create_list(user_id: int, title: str, description: str | None, is_public: bool) -> int:
    now = utcnow_iso()
    with transaction():
        total = fetch_one("SELECT COUNT(*) AS n FROM lists WHERE user_id = ?", (user_id,))["n"]
        if total >= MAX_LISTS_PER_USER:
            raise ApiError(409, "limit_reached", f"Você atingiu o limite de {MAX_LISTS_PER_USER} listas.")
        cursor = execute(
            "INSERT INTO lists (user_id, title, description, is_public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, description, int(is_public), now, now),
        )
        list_id = cursor.lastrowid
        execute(
            "INSERT INTO activities (user_id, type, list_id, created_at) VALUES (?, 'list_created', ?, ?)",
            (user_id, list_id, now),
        )
    return list_id  # type: ignore[return-value]


def update_list(list_id: int, changes: dict) -> None:
    allowed = {"title": "title", "description": "description", "is_public": "is_public"}
    sets, params = ["updated_at = ?"], [utcnow_iso()]
    for key, value in changes.items():
        sets.append(f"{allowed[key]} = ?")  # só chaves da lista fechada acima
        params.append(int(value) if key == "is_public" else value)
    with transaction():
        execute(f"UPDATE lists SET {', '.join(sets)} WHERE id = ?", (*params, list_id))


def delete_list(list_id: int) -> None:
    with transaction():
        execute("DELETE FROM lists WHERE id = ?", (list_id,))  # list_games e atividades saem em cascata


def _touch(list_id: int) -> None:
    execute("UPDATE lists SET updated_at = ? WHERE id = ?", (utcnow_iso(), list_id))


def add_game(list_id: int, game_id: int) -> None:
    with transaction():
        if fetch_one("SELECT 1 FROM list_games WHERE list_id = ? AND game_id = ?", (list_id, game_id)):
            raise ApiError(409, "already_in_list", "Este jogo já está na lista.")
        info = fetch_one(
            "SELECT COUNT(*) AS n, COALESCE(MAX(position), -1) AS last FROM list_games WHERE list_id = ?",
            (list_id,),
        )
        if info["n"] >= MAX_GAMES_PER_LIST:
            raise ApiError(409, "limit_reached", f"Uma lista comporta até {MAX_GAMES_PER_LIST} jogos.")
        execute(
            "INSERT INTO list_games (list_id, game_id, position, added_at) VALUES (?, ?, ?, ?)",
            (list_id, game_id, info["last"] + 1, utcnow_iso()),
        )
        _touch(list_id)


def _renumber(list_id: int) -> None:
    """Deixa as posições densas (0, 1, 2...) mantendo a ordem atual."""
    execute(
        "UPDATE list_games SET position = ("
        " SELECT COUNT(*) FROM list_games x WHERE x.list_id = list_games.list_id"
        " AND (x.position < list_games.position OR (x.position = list_games.position AND x.id < list_games.id))"
        ") WHERE list_id = ?",
        (list_id,),
    )


def remove_game(list_id: int, rawg_id: int) -> bool:
    with transaction():
        cursor = execute(
            "DELETE FROM list_games WHERE list_id = ? AND game_id = (SELECT id FROM games WHERE rawg_id = ?)",
            (list_id, rawg_id),
        )
        if cursor.rowcount == 0:
            return False
        _renumber(list_id)
        _touch(list_id)
    return True


def reorder(list_id: int, rawg_ids: list[int]) -> None:
    """Aplica a nova ordem. Precisa conter exatamente os jogos que já estão na lista."""
    with transaction():
        current = {
            row["rawg_id"]: row["game_id"]
            for row in fetch_all(
                "SELECT g.rawg_id, g.id AS game_id FROM list_games lg JOIN games g ON g.id = lg.game_id"
                " WHERE lg.list_id = ?",
                (list_id,),
            )
        }
        if len(set(rawg_ids)) != len(rawg_ids) or set(rawg_ids) != set(current):
            raise ApiError(
                422,
                "validation_error",
                "A nova ordem deve conter exatamente os jogos que já estão na lista, sem repetições.",
                fields={"rawg_ids": "Lista de jogos incompatível com a atual."},
            )
        for position, rawg_id in enumerate(rawg_ids):
            execute(
                "UPDATE list_games SET position = ? WHERE list_id = ? AND game_id = ?",
                (position, list_id, current[rawg_id]),
            )
        _touch(list_id)
