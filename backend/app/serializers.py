"""Converte linhas do SQLite em dicionários JSON.

As consultas SQL do projeto seguem um contrato de apelidos de coluna, que é o
que estas funções esperam:

  usuário   username, display_name, avatar_url            (+ bio, created_at)
  jogo      rawg_id, game_name, game_slug, cover_url      (+ release_date)
  review    review_id, rating, body, has_spoilers, review_created_at,
            review_updated_at, like_count, liked
  registro  status, is_favorite, started_at, completed_at, status_changed_at,
            entry_created_at, entry_updated_at, plays       (+ rating)
  atividade activity_id, type, activity_status, activity_is_replay,
            activity_created_at, review_*, list_id, list_title
"""
from __future__ import annotations

import sqlite3

from .services.rawg import thumb_url

EXCERPT_LENGTH = 280


def excerpt(body: str) -> str:
    return body[:EXCERPT_LENGTH].rstrip() + ("…" if len(body) > EXCERPT_LENGTH else "")


def _has(row: sqlite3.Row, key: str) -> bool:
    return key in row.keys()


def user_private(row: dict | sqlite3.Row) -> dict:
    """Dados da própria conta (inclui e-mail). Nunca usar para outros usuários."""
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "bio": row["bio"],
        "avatar_url": row["avatar_url"],
        "created_at": row["created_at"],
    }


def user_public(row: dict | sqlite3.Row) -> dict:
    data = {
        "username": row["username"],
        "display_name": row["display_name"],
        "avatar_url": row["avatar_url"],
    }
    keys = row.keys()
    if "bio" in keys:
        data["bio"] = row["bio"]
    if "created_at" in keys:
        data["created_at"] = row["created_at"]
    if "is_demo" in keys:
        data["is_demo"] = bool(row["is_demo"])
    return data


def game_out(rawg_id: int, name: str, slug: str, cover_url: str | None, release_date: str | None = None) -> dict:
    return {
        "rawg_id": rawg_id,
        "name": name,
        "slug": slug,
        "cover_url": cover_url,
        "cover_thumb_url": thumb_url(cover_url),
        "released": release_date,
    }


def game_from_row(row: sqlite3.Row) -> dict:
    return game_out(
        row["rawg_id"],
        row["game_name"],
        row["game_slug"],
        row["cover_url"],
        row["release_date"] if _has(row, "release_date") else None,
    )


def game_from_local(game: dict) -> dict:
    return game_out(game["rawg_id"], game["name"], game["slug"], game["cover_url"], game.get("release_date"))


def entry_from_row(row: sqlite3.Row) -> dict:
    return {
        "status": row["status"],
        "is_favorite": bool(row["is_favorite"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        # Quando o status mudou pela última vez ("Largado em ..."); `updated_at` muda também ao favoritar.
        "status_changed_at": row["status_changed_at"] or row["entry_updated_at"],
        "created_at": row["entry_created_at"],
        "updated_at": row["entry_updated_at"],
        "plays": row["plays"],
    }


def playthrough_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
    }


def review_from_row(row: sqlite3.Row, *, with_game: bool = True, with_user: bool = True) -> dict:
    data = {
        "id": row["review_id"],
        "rating": row["rating"],
        "body": row["body"],
        "has_spoilers": bool(row["has_spoilers"]),
        "created_at": row["review_created_at"],
        "updated_at": row["review_updated_at"],
        "like_count": row["like_count"],
        "liked": bool(row["liked"]),
    }
    if with_user:
        data["user"] = user_public(row)
    if with_game:
        data["game"] = game_from_row(row)
    return data


def list_summary_from_row(row: sqlite3.Row, covers: list[dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "is_public": bool(row["is_public"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "game_count": row["game_count"],
        "covers": covers,
        # Montado à mão: `created_at` desta linha é o da lista, não o do usuário.
        "owner": {
            "username": row["username"],
            "display_name": row["display_name"],
            "avatar_url": row["avatar_url"],
            "is_demo": bool(row["is_demo"]),
        },
    }


def activity_from_row(row: sqlite3.Row) -> dict:
    data: dict = {
        "id": row["activity_id"],
        "type": row["type"],
        "created_at": row["activity_created_at"],
        "user": user_public(row),
    }
    if row["type"] == "logged":
        data["status"] = row["activity_status"]
        data["replay"] = bool(row["activity_is_replay"])
        data["game"] = game_from_row(row)
    elif row["type"] == "reviewed":
        body = row["review_body"]
        spoilers = bool(row["review_has_spoilers"])
        data["game"] = game_from_row(row)
        data["review"] = {
            "id": row["review_id"],
            "rating": row["review_rating"],
            "has_spoilers": spoilers,
            # Trechos de reviews com spoilers nunca aparecem em feeds: só a nota e o aviso.
            "excerpt": excerpt(body) if body and not spoilers else None,
            "like_count": row["review_like_count"],
        }
    elif row["type"] == "list_created":
        data["list"] = {"id": row["list_id"], "title": row["list_title"]}
    return data
