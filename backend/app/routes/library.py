"""Diário pessoal do usuário autenticado."""
from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from ..auth import current_user, login_required
from ..db import fetch_one, transaction
from ..errors import ApiError
from ..security import rate_limit
from ..serializers import entry_from_row, game_from_local, game_from_row, playthrough_from_row
from ..services import games as games_service
from ..services import library as library_service
from ..services.library import STATUSES
from ..utils.pagination import page_args, page_envelope
from ..utils.validation import UNSET, FieldErrors, json_body, read_bool, read_client_today, read_date

bp = Blueprint("library", __name__, url_prefix="/api/library")

SORTS = {"recent", "name", "rating", "completed"}

MAX_STATUS_IDS = 80
_ID_LIST = re.compile(rf"^\d+(,\d+){{0,{MAX_STATUS_IDS - 1}}}$")


def entry_item(row) -> dict:
    return {"game": game_from_row(row), "entry": entry_from_row(row), "rating": row["rating"]}


def counts_for(user_id: int) -> dict:
    row = fetch_one(
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(status = 'quero_jogar'), 0) AS quero_jogar,"
        " COALESCE(SUM(status = 'jogando'), 0) AS jogando,"
        " COALESCE(SUM(status = 'zerado'), 0) AS zerado,"
        " COALESCE(SUM(status = 'abandonado'), 0) AS abandonado,"
        " COALESCE(SUM(status = 'pausado'), 0) AS pausado,"
        " COALESCE(SUM(is_favorite), 0) AS favorites"
        " FROM library_entries WHERE user_id = ?",
        (user_id,),
    )
    return dict(row)


def library_page(user_id: int) -> dict:
    """Listagem paginada com filtros (?status=, ?favorites=1, ?sort=). Usada também pelos perfis."""
    page, per_page = page_args(default_per_page=24, max_per_page=60)
    status = request.args.get("status") or None
    if status is not None and status not in STATUSES:
        raise ApiError(400, "invalid_parameter", "Status inválido. Use: " + ", ".join(STATUSES) + ".")
    sort = request.args.get("sort", "recent")
    if sort not in SORTS:
        raise ApiError(400, "invalid_parameter", "Ordenação inválida. Use: " + ", ".join(sorted(SORTS)) + ".")
    rows = library_service.list_entries(
        user_id,
        status=status,
        favorites_only=request.args.get("favorites") in {"1", "true"},
        sort=sort,
        limit=per_page + 1,
        offset=(page - 1) * per_page,
    )
    data = page_envelope(rows, page, per_page, [entry_item(r) for r in rows[:per_page]])
    data["counts"] = counts_for(user_id)
    return data


@bp.get("")
@login_required
def my_library():
    return jsonify(library_page(current_user()["id"]))


@bp.get("/status")
@login_required
@rate_limit("library-status", 120, 60)
def statuses():
    """Quais destes jogos (?ids=1,2,3) já estão no diário de quem pergunta, e com que status. Os cards do catálogo usam."""
    raw = (request.args.get("ids") or "").strip()
    if raw and not _ID_LIST.match(raw):
        raise ApiError(400, "invalid_parameter", f"Parâmetro 'ids' inválido: informe até {MAX_STATUS_IDS} números separados por vírgula.")
    ids = [int(value) for value in raw.split(",")] if raw else []
    return jsonify({"items": library_service.statuses_for(current_user()["id"], ids)})


def _read_changes(data: dict) -> dict:
    errors = FieldErrors()
    changes: dict = {}
    if "status" in data:
        if data["status"] in STATUSES:
            changes["status"] = data["status"]
        else:
            errors.add("status", "Escolha um status válido.")
    for key, label in (("started_at", "A data de início"), ("completed_at", "A data de término")):
        value = read_date(data, key, label, errors)
        if value is not UNSET:
            changes[key] = value
    favorite = read_bool(data, "is_favorite", "Favorito", errors)
    if favorite is not UNSET:
        changes["is_favorite"] = favorite
    today = read_client_today(data, errors)
    if today is not None:
        changes["today"] = today
    errors.raise_if_any()
    return changes


@bp.put("/<int:rawg_id>")
@login_required
def save_entry(rawg_id: int):
    """Cria ou atualiza o registro do jogo. Só os campos enviados mudam."""
    data = json_body()
    changes = _read_changes(data)
    # "Só se for novo": os atalhos dos cards (guardar na fila) nunca podem mexer num jogo que já está no diário,
    # por exemplo se ele foi registrado em outra aba depois que a página carregou.
    create_only = data.get("create_only") is True
    game = games_service.ensure_game(rawg_id)  # consulta a RAWG antes de abrir transação de escrita
    user_id = current_user()["id"]
    with transaction():
        if create_only and library_service.get_entry(user_id, game["id"]):
            raise ApiError(409, "already_in_diary", "Este jogo já está no seu diário.")
        entry, created = library_service.upsert_entry(user_id, game, **changes)
    response = jsonify({"game": game_from_local(game), "entry": entry_from_row(entry), "rating": entry["rating"]})
    response.status_code = 201 if created else 200
    return response


def _entry_with_history(user_id: int, game: dict, entry) -> dict:
    return {
        "game": game_from_local(game),
        "entry": entry_from_row(entry),
        "rating": entry["rating"],
        "playthroughs": [playthrough_from_row(r) for r in library_service.list_playthroughs(user_id, game["id"])],
    }


@bp.post("/<int:rawg_id>/replay")
@login_required
@rate_limit("library-write", 60, 60)
def replay(rawg_id: int):
    """"Jogar de novo": guarda a jogada atual no histórico do jogo e começa outra."""
    data = json_body()
    errors = FieldErrors()
    today = read_client_today(data, errors)
    errors.raise_if_any()
    user_id = current_user()["id"]
    game = games_service.get_local_game(rawg_id)
    if game is None:
        raise ApiError(404, "not_found", "Este jogo não está no seu diário.")
    entry = library_service.replay_entry(user_id, game["id"], today=today)
    response = jsonify(_entry_with_history(user_id, game, entry))
    response.status_code = 201
    return response


@bp.delete("/<int:rawg_id>/playthroughs/<int:playthrough_id>")
@login_required
def remove_playthrough(rawg_id: int, playthrough_id: int):
    user_id = current_user()["id"]
    game = games_service.get_local_game(rawg_id)
    if game is None or not library_service.delete_playthrough(user_id, game["id"], playthrough_id):
        raise ApiError(404, "not_found", "Jogada não encontrada.")
    entry = library_service.get_entry(user_id, game["id"])
    return jsonify(_entry_with_history(user_id, game, entry))


@bp.delete("/<int:rawg_id>")
@login_required
def remove_entry(rawg_id: int):
    data = request.get_json(silent=True)  # opcional: {"with_review": true} confirma que a nota sai junto
    confirmed = isinstance(data, dict) and data.get("with_review") is True
    game = games_service.get_local_game(rawg_id)
    result = library_service.delete_entry(current_user()["id"], game["id"], confirm_review=confirmed) if game else None
    if result is None:
        raise ApiError(404, "not_found", "Este jogo não está na sua biblioteca.")
    return jsonify({"ok": True, **result})
