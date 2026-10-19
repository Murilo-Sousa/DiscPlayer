"""Atividade da comunidade e feed de quem o usuário segue."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import current_user, login_required, viewer_id
from ..serializers import activity_from_row
from ..services import feed as feed_service
from ..utils.pagination import page_args, page_envelope

bp = Blueprint("feed", __name__, url_prefix="/api")


@bp.get("/activity")
def community_activity():
    """Atividade recente de todos os jogadores (listas privadas ficam de fora)."""
    page, per_page = page_args(default_per_page=12, max_per_page=50)
    rows = feed_service.activities(
        "global", viewer_id=viewer_id(), limit=per_page + 1, offset=(page - 1) * per_page
    )
    return jsonify(page_envelope(rows, page, per_page, [activity_from_row(r) for r in rows[:per_page]]))


@bp.get("/feed")
@login_required
def following_feed():
    """Atividade de quem o usuário segue, da mais recente para a mais antiga."""
    page, per_page = page_args(default_per_page=20, max_per_page=50)
    rows = feed_service.activities(
        "following", viewer_id=current_user()["id"], limit=per_page + 1, offset=(page - 1) * per_page
    )
    return jsonify(page_envelope(rows, page, per_page, [activity_from_row(r) for r in rows[:per_page]]))
