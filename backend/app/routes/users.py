"""Perfis públicos, estatísticas e relações de seguir.

Tudo aqui é público por definição (o que o jogador registrou no diário, as reviews
e as listas públicas). E-mail e listas privadas nunca saem destas rotas.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import current_user, login_required, viewer_id
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import activity_from_row, review_from_row, user_public
from ..services import feed as feed_service
from ..services import library as library_service
from ..services import lists as lists_service
from ..services import profiles as profiles_service
from ..services import reviews as reviews_service
from ..utils.pagination import page_args, page_envelope
from .library import entry_item, library_page
from .lists import summaries

bp = Blueprint("users", __name__, url_prefix="/api/users")


def _target(username: str):
    row = profiles_service.get_by_username(username)
    if row is None:
        raise ApiError(404, "not_found", "Jogador não encontrado.")
    return row


@bp.get("/<username>")
def profile(username: str):
    user = _target(username)
    viewer = viewer_id()
    is_self = viewer == user["id"]
    favorites = library_service.list_entries(user["id"], favorites_only=True, limit=8)
    recent = library_service.list_entries(user["id"], limit=12)
    return jsonify(
        {
            "user": user_public(user),
            "stats": profiles_service.stats_for(user["id"], include_private_lists=is_self),
            "viewer": {"is_self": is_self, "is_following": profiles_service.is_following(viewer, user["id"])},
            "favorites": [entry_item(r) for r in favorites],
            "recent": [entry_item(r) for r in recent],
        }
    )


@bp.get("/<username>/library")
def library(username: str):
    return jsonify(library_page(_target(username)["id"]))


@bp.get("/<username>/reviews")
def reviews(username: str):
    user = _target(username)
    page, per_page = page_args(default_per_page=10, max_per_page=30)
    rows = reviews_service.list_for_user(
        user["id"], viewer_id(), limit=per_page + 1, offset=(page - 1) * per_page
    )
    return jsonify(
        page_envelope(rows, page, per_page, [review_from_row(r, with_user=False) for r in rows[:per_page]])
    )


@bp.get("/<username>/lists")
def lists(username: str):
    user = _target(username)
    rows = lists_service.lists_of_user(user["id"], include_private=viewer_id() == user["id"], limit=100)
    return jsonify({"items": summaries(rows)})


@bp.get("/<username>/activity")
def activity(username: str):
    user = _target(username)
    page, per_page = page_args(default_per_page=20, max_per_page=50)
    rows = feed_service.activities(
        "user", viewer_id=viewer_id(), target_id=user["id"], limit=per_page + 1, offset=(page - 1) * per_page
    )
    return jsonify(page_envelope(rows, page, per_page, [activity_from_row(r) for r in rows[:per_page]]))


def _follow_list(username: str, direction: str):
    user = _target(username)
    page, per_page = page_args(default_per_page=30, max_per_page=60)
    rows = profiles_service.list_follows(user["id"], direction, limit=per_page + 1, offset=(page - 1) * per_page)
    return jsonify(page_envelope(rows, page, per_page, [user_public(r) for r in rows[:per_page]]))


@bp.get("/<username>/followers")
def followers(username: str):
    return _follow_list(username, "followers")


@bp.get("/<username>/following")
def following(username: str):
    return _follow_list(username, "following")


def _set_follow(username: str, follow: bool):
    target = _target(username)
    total = profiles_service.set_follow(current_user()["id"], target["id"], follow)
    return jsonify({"following": follow, "followers": total})


@bp.put("/<username>/follow")
@login_required
@rate_limit("follow", 60, 60)
def follow(username: str):
    return _set_follow(username, True)


@bp.delete("/<username>/follow")
@login_required
@rate_limit("follow", 60, 60)
def unfollow(username: str):
    return _set_follow(username, False)
