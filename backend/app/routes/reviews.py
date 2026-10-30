"""Reviews: criar, editar, excluir e curtir. A nota (0 a 10, passos de 0,5) é obrigatória; o texto e o aviso de spoilers, não.

Só avalia quem já começou o jogo (jogando, pausado, abandonado ou zerado): veja `services/library.py`."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import current_user, login_required, viewer_id
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import review_from_row
from ..services import games as games_service
from ..services import reviews as reviews_service
from ..services.reviews import KEEP
from ..utils.pagination import page_args, page_envelope
from ..utils.validation import UNSET, FieldErrors, json_body, read_bool, read_client_today, read_rating, read_text

bp = Blueprint("reviews", __name__, url_prefix="/api")

REVIEW_MAX_LENGTH = 5000


def _not_found():
    return ApiError(404, "not_found", "Review não encontrada.")


def _require_author(review_id: int) -> None:
    """404 se a review não existe; 403 se pertence a outra pessoa."""
    author_id = reviews_service.get_author_id(review_id)
    if author_id is None:
        raise _not_found()
    if author_id != current_user()["id"]:
        raise ApiError(403, "forbidden", "Você só pode alterar as suas próprias reviews.")


@bp.get("/reviews")
def recent_reviews():
    """Reviews com texto mais recentes da comunidade."""
    page, per_page = page_args(default_per_page=10, max_per_page=30)
    rows = reviews_service.list_recent(viewer_id(), limit=per_page + 1, offset=(page - 1) * per_page)
    return jsonify(page_envelope(rows, page, per_page, [review_from_row(r) for r in rows[:per_page]]))


@bp.get("/reviews/<int:review_id>")
def get_review(review_id: int):
    row = reviews_service.get_review(review_id, viewer_id())
    if row is None:
        raise _not_found()
    return jsonify({"review": review_from_row(row)})


@bp.post("/games/<int:rawg_id>/reviews")
@login_required
@rate_limit("review-write", 60, 60)
def create_review(rawg_id: int):
    data = json_body()
    errors = FieldErrors()
    rating = read_rating(data, errors, required=True)
    body = read_text(data, "body", "A review", errors, max_len=REVIEW_MAX_LENGTH, multiline=True)
    spoilers = read_bool(data, "has_spoilers", "O aviso de spoilers", errors)
    today = read_client_today(data, errors)  # o "hoje" de quem usa o site decide se o jogo já saiu
    errors.raise_if_any()
    user = current_user()
    game = games_service.ensure_game(rawg_id)  # metadados vêm da RAWG, nunca do cliente
    review_id = reviews_service.create_review(
        user["id"],
        game,
        rating,
        None if body is UNSET else body,
        False if spoilers is UNSET else spoilers,
        today=today,
    )
    row = reviews_service.get_review(review_id, user["id"])
    response = jsonify({"review": review_from_row(row)})
    response.status_code = 201
    return response


@bp.patch("/reviews/<int:review_id>")
@login_required
@rate_limit("review-write", 60, 60)
def update_review(review_id: int):
    data = json_body()
    errors = FieldErrors()
    rating = read_rating(data, errors)
    body = read_text(data, "body", "A review", errors, max_len=REVIEW_MAX_LENGTH, multiline=True)
    spoilers = read_bool(data, "has_spoilers", "O aviso de spoilers", errors)
    if rating is UNSET and body is UNSET and spoilers is UNSET and not errors:
        errors.add("rating", "Envie a nota, o texto ou o aviso de spoilers para atualizar a review.")
    errors.raise_if_any()
    _require_author(review_id)
    reviews_service.update_review(
        review_id,
        rating=None if rating is UNSET else rating,
        body=KEEP if body is UNSET else body,  # None limpa o texto e mantém só a nota
        has_spoilers=KEEP if spoilers is UNSET else spoilers,
    )
    return jsonify({"review": review_from_row(reviews_service.get_review(review_id, current_user()["id"]))})


@bp.delete("/reviews/<int:review_id>")
@login_required
def delete_review(review_id: int):
    _require_author(review_id)
    reviews_service.delete_review(review_id)
    return jsonify({"ok": True})


def _set_like(review_id: int, liked: bool):
    user = current_user()
    author_id = reviews_service.get_author_id(review_id)
    if author_id is None:
        raise _not_found()
    if author_id == user["id"]:
        raise ApiError(400, "cannot_like_own", "Você não pode curtir a sua própria review.")
    total = reviews_service.set_like(user["id"], review_id, liked)
    return jsonify({"liked": liked, "like_count": total})


@bp.put("/reviews/<int:review_id>/like")
@login_required
@rate_limit("like", 120, 60)
def like(review_id: int):
    return _set_like(review_id, True)


@bp.delete("/reviews/<int:review_id>/like")
@login_required
@rate_limit("like", 120, 60)
def unlike(review_id: int):
    return _set_like(review_id, False)
