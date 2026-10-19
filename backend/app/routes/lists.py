"""Listas personalizadas: criação, edição, jogos, ordem e visibilidade."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..auth import current_user, login_required, viewer_id
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import game_from_row, list_summary_from_row
from ..services import games as games_service
from ..services import lists as lists_service
from ..utils.pagination import page_args, page_envelope
from ..utils.validation import UNSET, FieldErrors, json_body, read_bool, read_text

bp = Blueprint("lists", __name__, url_prefix="/api")


def summaries(rows) -> list[dict]:
    covers = lists_service.covers_for([r["id"] for r in rows])
    return [list_summary_from_row(r, covers[r["id"]]) for r in rows]


def _detail(row) -> dict:
    data = summaries([row])[0]
    data["is_owner"] = row["owner_id"] == viewer_id()
    data["items"] = [
        {"position": item["position"], "added_at": item["added_at"], "game": game_from_row(item)}
        for item in lists_service.list_items(row["id"])
    ]
    return data


def _rawg_id(data: dict, errors: FieldErrors) -> int | None:
    value = data.get("rawg_id")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.add("rawg_id", "Informe o identificador do jogo.")
        return None
    return value


@bp.get("/lists")
def community_lists():
    """Listas públicas da comunidade (só as que já têm jogos)."""
    page, per_page = page_args(default_per_page=12, max_per_page=30)
    query = (request.args.get("q") or "").strip()[:100] or None
    rows = lists_service.community_lists(query=query, limit=per_page + 1, offset=(page - 1) * per_page)
    return jsonify(page_envelope(rows, page, per_page, summaries(rows[:per_page])))


@bp.get("/me/lists")
@login_required
def my_lists():
    """Todas as listas do usuário, inclusive as privadas."""
    rows = lists_service.lists_of_user(current_user()["id"], include_private=True, limit=100)
    return jsonify({"items": summaries(rows)})


@bp.post("/lists")
@login_required
@rate_limit("list-write", 60, 60)
def create_list():
    data = json_body()
    errors = FieldErrors()
    title = read_text(data, "title", "O título", errors, required=True, max_len=80)
    description = read_text(data, "description", "A descrição", errors, max_len=500, multiline=True)
    is_public = read_bool(data, "is_public", "Visibilidade", errors)
    errors.raise_if_any()
    list_id = lists_service.create_list(
        current_user()["id"],
        title,
        None if description is UNSET else description,
        True if is_public is UNSET else is_public,
    )
    response = jsonify({"list": _detail(lists_service.get_visible(list_id, current_user()["id"]))})
    response.status_code = 201
    return response


@bp.get("/lists/<int:list_id>")
def get_list(list_id: int):
    row = lists_service.get_visible(list_id, viewer_id())  # lista privada de outra pessoa = 404
    if row is None:
        raise ApiError(404, "not_found", "Lista não encontrada.")
    return jsonify({"list": _detail(row)})


@bp.patch("/lists/<int:list_id>")
@login_required
def update_list(list_id: int):
    user = current_user()
    data = json_body()
    errors = FieldErrors()
    changes: dict = {}
    if "title" in data:
        title = read_text(data, "title", "O título", errors, required=True, max_len=80)
        if title is not UNSET:
            changes["title"] = title
    if "description" in data:
        description = read_text(data, "description", "A descrição", errors, max_len=500, multiline=True)
        if description is not UNSET:
            changes["description"] = description
    is_public = read_bool(data, "is_public", "Visibilidade", errors)
    if is_public is not UNSET:
        changes["is_public"] = is_public
    errors.raise_if_any()
    lists_service.get_owned(list_id, user["id"])
    if changes:
        lists_service.update_list(list_id, changes)
    return jsonify({"list": _detail(lists_service.get_visible(list_id, user["id"]))})


@bp.delete("/lists/<int:list_id>")
@login_required
def delete_list(list_id: int):
    lists_service.get_owned(list_id, current_user()["id"])
    lists_service.delete_list(list_id)
    return jsonify({"ok": True})


@bp.post("/lists/<int:list_id>/games")
@login_required
@rate_limit("list-write", 60, 60)
def add_game(list_id: int):
    user = current_user()
    data = json_body()
    errors = FieldErrors()
    rawg_id = _rawg_id(data, errors)
    errors.raise_if_any()
    lists_service.get_owned(list_id, user["id"])
    game = games_service.ensure_game(rawg_id)  # type: ignore[arg-type]
    lists_service.add_game(list_id, game["id"])
    response = jsonify({"list": _detail(lists_service.get_visible(list_id, user["id"]))})
    response.status_code = 201
    return response


@bp.delete("/lists/<int:list_id>/games/<int:rawg_id>")
@login_required
def remove_game(list_id: int, rawg_id: int):
    user = current_user()
    lists_service.get_owned(list_id, user["id"])
    if not lists_service.remove_game(list_id, rawg_id):
        raise ApiError(404, "not_found", "Este jogo não está na lista.")
    return jsonify({"list": _detail(lists_service.get_visible(list_id, user["id"]))})


@bp.put("/lists/<int:list_id>/order")
@login_required
def reorder_games(list_id: int):
    user = current_user()
    data = json_body()
    rawg_ids = data.get("rawg_ids")
    if (
        not isinstance(rawg_ids, list)
        or len(rawg_ids) > lists_service.MAX_GAMES_PER_LIST
        or not all(isinstance(i, int) and not isinstance(i, bool) for i in rawg_ids)
    ):
        raise ApiError(
            422,
            "validation_error",
            "Revise os campos destacados.",
            fields={"rawg_ids": "Envie a lista de identificadores dos jogos na nova ordem."},
        )
    lists_service.get_owned(list_id, user["id"])
    lists_service.reorder(list_id, rawg_ids)
    return jsonify({"list": _detail(lists_service.get_visible(list_id, user["id"]))})
