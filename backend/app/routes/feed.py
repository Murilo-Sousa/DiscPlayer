"""Atividade da comunidade e feed de quem o usuário segue."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..auth import current_user, login_required, viewer_id
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import activity_from_row
from ..services import feed as feed_service
from ..services import home as home_service
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


def _home_scope() -> str:
    scope = request.args.get("scope", "community")
    if scope not in home_service.SCOPES:
        raise ApiError(400, "invalid_parameter", "O parâmetro 'scope' deve ser 'following' ou 'community'.")
    return scope


@bp.get("/playing")
@login_required
@rate_limit("home-feed", 120, 60)
def playing_now():
    """"Jogando agora" do início: um cartão por pessoa (quem o usuário segue ou a comunidade), sem o próprio usuário."""
    scope = _home_scope()
    _, per_page = page_args(default_per_page=12, max_per_page=24)
    return jsonify(home_service.playing_now(current_user()["id"], scope, per_page))


@bp.get("/highlights")
@login_required
@rate_limit("home-feed", 120, 60)
def highlights():
    """Novidades do início: a atividade recente já agrupada em cartões (zerou e avaliou juntos, fila em lote...)."""
    scope = _home_scope()
    _, per_page = page_args(default_per_page=10, max_per_page=20)
    return jsonify(home_service.highlights(current_user()["id"], scope, per_page))
