"""Diário pessoal: uma entrada por usuário e jogo (a jogada atual), com histórico em `activities`.

Jogadas anteriores do mesmo jogo ficam em `playthroughs`: "jogar de novo" guarda o
status e as datas da entrada ali e recomeça a entrada. A nota continua única por jogo.
"""
from __future__ import annotations

import sqlite3

from ..db import execute, fetch_all, fetch_one, transaction
from ..errors import ApiError
from ..utils.dates import today_utc, utcnow_iso
from ..utils.validation import UNSET

STATUSES = ("quero_jogar", "jogando", "zerado", "abandonado", "pausado")
# Só dá para recomeçar um jogo cuja jogada atual já terminou ou foi interrompida.
REPLAYABLE = ("zerado", "abandonado", "pausado")

ENTRY_COLUMNS = """
    e.status, e.is_favorite, e.started_at, e.completed_at,
    e.created_at AS entry_created_at, e.updated_at AS entry_updated_at,
    1 + (SELECT COUNT(*) FROM playthroughs p
          WHERE p.user_id = e.user_id AND p.game_id = e.game_id) AS plays,
    g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,
    (SELECT rv.rating FROM reviews rv
      WHERE rv.user_id = e.user_id AND rv.game_id = e.game_id) AS rating
"""

_SORTS = {
    "recent": "e.updated_at DESC, e.id DESC",
    "name": "g.name COLLATE NOCASE ASC, e.id ASC",
    "rating": "rating IS NULL, rating DESC, e.updated_at DESC",
    "completed": "e.completed_at IS NULL, e.completed_at DESC, e.updated_at DESC",
}


def get_entry(user_id: int, game_id: int) -> sqlite3.Row | None:
    return fetch_one(
        f"SELECT {ENTRY_COLUMNS} FROM library_entries e JOIN games g ON g.id = e.game_id"
        " WHERE e.user_id = ? AND e.game_id = ?",
        (user_id, game_id),
    )


def list_entries(
    user_id: int,
    *,
    status: str | None = None,
    favorites_only: bool = False,
    sort: str = "recent",
    limit: int = 20,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Linhas do diário de um usuário (pede-se limit+1 para detectar próxima página)."""
    where = ["e.user_id = ?"]
    params: list = [user_id]
    if status:
        where.append("e.status = ?")
        params.append(status)
    if favorites_only:
        where.append("e.is_favorite = 1")
    order = _SORTS.get(sort, _SORTS["recent"])
    return fetch_all(
        f"SELECT {ENTRY_COLUMNS} FROM library_entries e JOIN games g ON g.id = e.game_id"
        f" WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )


def upsert_entry(
    user_id: int,
    game: dict,
    *,
    status=UNSET,
    is_favorite=UNSET,
    started_at=UNSET,
    completed_at=UNSET,
    today: str | None = None,
) -> tuple[sqlite3.Row, bool]:
    """Cria ou atualiza a entrada do jogo. Devolve (entrada, foi_criada).

    Regras:
      * só existe uma entrada por (usuário, jogo); registrar de novo atualiza;
      * o status é obrigatório na criação e opcional nas atualizações;
      * mudar o status registra uma atividade ("logged"). Zerar o mesmo jogo
        duas vezes gera duas atividades, mas continua uma única entrada;
      * ao passar para "jogando" sem data de início (ou "zerado" sem data de
        término), a data de hoje é preenchida — o cliente pode enviar a sua e
        também pode informar o "hoje" do fuso dele (`today`; sem ele, vale UTC);
      * a data de término não pode ser anterior à de início.
    """
    game_id = game["id"]
    created = False
    with transaction():
        current = fetch_one(
            "SELECT * FROM library_entries WHERE user_id = ? AND game_id = ?", (user_id, game_id)
        )
        now = utcnow_iso()
        if current is None:
            if status is UNSET:
                raise ApiError(
                    422,
                    "validation_error",
                    "Revise os campos destacados.",
                    fields={"status": "Escolha um status para registrar o jogo."},
                )
            new_status = status
            new_favorite = False if is_favorite is UNSET else is_favorite
            new_started = None if started_at is UNSET else started_at
            new_completed = None if completed_at is UNSET else completed_at
        else:
            new_status = current["status"] if status is UNSET else status
            new_favorite = bool(current["is_favorite"]) if is_favorite is UNSET else is_favorite
            new_started = current["started_at"] if started_at is UNSET else started_at
            new_completed = current["completed_at"] if completed_at is UNSET else completed_at

        status_changed = current is None or new_status != current["status"]
        if status_changed:
            fill_date = today or today_utc().isoformat()
            if new_status == "jogando" and started_at is UNSET and new_started is None:
                new_started = fill_date
            if new_status == "zerado" and completed_at is UNSET and new_completed is None:
                new_completed = fill_date

        if new_started and new_completed and new_completed < new_started:
            raise ApiError(
                422,
                "validation_error",
                "Revise os campos destacados.",
                fields={"completed_at": "A data de término não pode ser anterior à data de início."},
            )

        if current is None:
            execute(
                "INSERT INTO library_entries"
                " (user_id, game_id, status, is_favorite, started_at, completed_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, game_id, new_status, int(new_favorite), new_started, new_completed, now, now),
            )
            created = True
        else:
            execute(
                "UPDATE library_entries SET status = ?, is_favorite = ?, started_at = ?,"
                " completed_at = ?, updated_at = ? WHERE id = ?",
                (new_status, int(new_favorite), new_started, new_completed, now, current["id"]),
            )
        if status_changed:
            execute(
                "INSERT INTO activities (user_id, type, game_id, status, created_at)"
                " VALUES (?, 'logged', ?, ?, ?)",
                (user_id, game_id, new_status, now),
            )
    return get_entry(user_id, game_id), created  # type: ignore[return-value]


def delete_entry(user_id: int, game_id: int) -> bool:
    """Remove a entrada, as jogadas anteriores e o rastro delas no histórico. A review (se houver) permanece."""
    with transaction():
        cursor = execute(
            "DELETE FROM library_entries WHERE user_id = ? AND game_id = ?", (user_id, game_id)
        )
        if cursor.rowcount == 0:
            return False
        execute("DELETE FROM playthroughs WHERE user_id = ? AND game_id = ?", (user_id, game_id))
        execute(
            "DELETE FROM activities WHERE user_id = ? AND game_id = ? AND type = 'logged'",
            (user_id, game_id),
        )
    return True


def list_playthroughs(user_id: int, game_id: int) -> list[sqlite3.Row]:
    """Jogadas anteriores do jogo, da mais antiga para a mais recente."""
    return fetch_all(
        "SELECT id, status, started_at, completed_at, created_at FROM playthroughs"
        " WHERE user_id = ? AND game_id = ? ORDER BY id ASC",
        (user_id, game_id),
    )


def replay_entry(user_id: int, game_id: int, *, today: str | None = None) -> sqlite3.Row:
    """Guarda a jogada atual no histórico e começa outra ("jogar de novo").

    A entrada volta a "jogando", com início em hoje e sem data de término; o favorito
    continua. Só vale para jogos zerados, abandonados ou pausados: clicar duas vezes
    seguidas não cria uma jogada fantasma, porque depois do primeiro clique o status já
    é "jogando".
    """
    with transaction():
        current = fetch_one(
            "SELECT * FROM library_entries WHERE user_id = ? AND game_id = ?", (user_id, game_id)
        )
        if current is None:
            raise ApiError(404, "not_found", "Este jogo não está no seu diário.")
        if current["status"] not in REPLAYABLE:
            raise ApiError(
                409,
                "cannot_replay",
                "Só dá para jogar de novo um jogo que você já zerou, abandonou ou pausou.",
            )
        now = utcnow_iso()
        execute(
            "INSERT INTO playthroughs (user_id, game_id, status, started_at, completed_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, game_id, current["status"], current["started_at"], current["completed_at"], now),
        )
        execute(
            "UPDATE library_entries SET status = 'jogando', started_at = ?, completed_at = NULL,"
            " updated_at = ? WHERE id = ?",
            (today or today_utc().isoformat(), now, current["id"]),
        )
        execute(
            "INSERT INTO activities (user_id, type, game_id, status, is_replay, created_at)"
            " VALUES (?, 'logged', ?, 'jogando', 1, ?)",
            (user_id, game_id, now),
        )
    return get_entry(user_id, game_id)  # type: ignore[return-value]


def delete_playthrough(user_id: int, game_id: int, playthrough_id: int) -> bool:
    """Exclui uma jogada anterior (só se for do próprio usuário e do jogo informado)."""
    with transaction():
        cursor = execute(
            "DELETE FROM playthroughs WHERE id = ? AND user_id = ? AND game_id = ?",
            (playthrough_id, user_id, game_id),
        )
    return cursor.rowcount > 0
