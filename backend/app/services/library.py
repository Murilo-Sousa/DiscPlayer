"""Diário pessoal: uma entrada por usuário e jogo (a jogada atual), com histórico em `activities`.

Jogadas anteriores do mesmo jogo ficam em `playthroughs`: "jogar de novo" guarda o
status e as datas da entrada ali e recomeça a entrada. A nota continua única por jogo.

O que cada status permite (as regras abaixo valem no servidor; o front-end as espelha em
`frontend/src/utils/diary.js`, e um teste confere que as duas listas não se separam):

  * "Quero jogar" é um jogo que a pessoa ainda NÃO começou: não tem data de início, data de
    término, favorito, nota nem review;
  * data de início, favorito, nota e review pertencem a quem já começou o jogo
    (jogando, pausado, abandonado ou zerado);
  * data de término só existe em jogo ZERADO;
  * jogo que ainda não foi lançado só pode ficar em "Quero jogar";
  * "jogar de novo" só vale para jogo zerado ou abandonado (para retomar um jogo pausado, basta
    voltar para "Jogando").
"""
from __future__ import annotations

import sqlite3

from ..db import execute, fetch_all, fetch_one, transaction
from ..errors import ApiError
from ..utils.dates import max_allowed_date, parse_iso_date, today_utc, utcnow_iso
from ..utils.validation import UNSET, FieldErrors

STATUSES = ("quero_jogar", "jogando", "zerado", "abandonado", "pausado")
# A pessoa já começou o jogo: só nesses status há data de início, favorito, nota e review.
STARTED = ("jogando", "pausado", "abandonado", "zerado")
# Só um jogo zerado tem data de término.
COMPLETABLE = ("zerado",)
# Só dá para recomeçar um jogo cuja jogada atual terminou ou foi largada.
REPLAYABLE = ("zerado", "abandonado")

ENTRY_COLUMNS = """
    e.status, e.is_favorite, e.started_at, e.completed_at, e.status_changed_at,
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


def _given(value) -> bool:
    """O campo veio na requisição com um valor (nem ausente, nem null)."""
    return value is not UNSET and value is not None


def _br_date(iso: str) -> str:
    parsed = parse_iso_date(iso)
    return parsed.strftime("%d/%m/%Y") if parsed else iso


def release_block(game: dict, today: str | None = None) -> str | None:
    """A data de lançamento (AAAA-MM-DD) se o jogo ainda não saiu; None se já saiu ou se ninguém sabe a data.

    Sem o "hoje" de quem usa o site, vale UTC mais um dia: o servidor não rejeita ninguém por causa de fuso.
    """
    released = game.get("release_date")
    limit = today or max_allowed_date().isoformat()
    return released if released and released > limit else None


def _require_released(game: dict, today: str | None) -> None:
    released = release_block(game, today)
    if released:
        raise ApiError(
            409,
            "not_released",
            f"Este jogo só será lançado em {_br_date(released)}. Até lá, só dá para colocá-lo em “Quero jogar”.",
        )


def _require_not_played(user_id: int, game_id: int) -> None:
    """Um jogo com nota ou jogadas anteriores já foi jogado: não volta para "Quero jogar"."""
    if fetch_one("SELECT 1 FROM reviews WHERE user_id = ? AND game_id = ?", (user_id, game_id)):
        raise ApiError(
            409,
            "already_played",
            "Você já avaliou este jogo, então ele não volta para “Quero jogar”. Exclua a sua nota antes, se for o caso.",
        )
    if fetch_one("SELECT 1 FROM playthroughs WHERE user_id = ? AND game_id = ?", (user_id, game_id)):
        raise ApiError(
            409,
            "already_played",
            "Este jogo já tem jogadas anteriores no seu histórico, então ele não volta para “Quero jogar”.",
        )


def require_can_rate(user_id: int, game: dict, today: str | None = None) -> None:
    """Só quem já começou o jogo avalia (nota e review). Levanta 409 com o motivo, se não for o caso."""
    released = release_block(game, today)
    if released:
        raise ApiError(
            409,
            "not_released",
            f"Este jogo só será lançado em {_br_date(released)}. Dá para avaliar depois que você jogar.",
        )
    entry = fetch_one("SELECT status FROM library_entries WHERE user_id = ? AND game_id = ?", (user_id, game["id"]))
    if entry is None:
        raise ApiError(
            409,
            "not_played",
            "Registre o jogo no seu diário como Jogando, Pausado, Abandonado ou Zerado para poder avaliá-lo.",
        )
    if entry["status"] not in STARTED:
        raise ApiError(
            409,
            "not_played",
            "Você marcou este jogo como “Quero jogar”. Só dá para avaliar um jogo que você já começou.",
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
      * a data de término não pode ser anterior à de início;
      * o status decide o que a entrada pode ter (veja o topo do módulo): "Quero jogar" não tem
        datas nem favorito, só "zerado" tem data de término, e um jogo que ainda não saiu só fica
        em "Quero jogar". Ao mudar de status, o que deixou de valer é limpo (sair de "zerado"
        apaga a data de término; voltar a "Quero jogar" apaga as datas e o favorito). Enviar um valor
        que o status não aceita é erro, em vez de ser ignorado em silêncio;
      * um jogo com nota ou jogadas anteriores não volta para "Quero jogar".
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
            if new_status == "quero_jogar":
                _require_not_played(user_id, game_id)
            else:
                _require_released(game, today)

        errors = FieldErrors()
        if new_status not in STARTED:  # "Quero jogar": ainda não começou
            if _given(started_at):
                errors.add("started_at", "Um jogo que você ainda não começou não tem data de início. Mude o status antes.")
            if _given(completed_at):
                errors.add("completed_at", "Um jogo que você ainda não começou não tem data de término.")
            if is_favorite is True:
                raise ApiError(409, "cannot_favorite", "Só dá para favoritar um jogo que você já começou.")
            new_started, new_completed, new_favorite = None, None, False
        elif new_status not in COMPLETABLE:
            if _given(completed_at):
                errors.add("completed_at", "Só um jogo zerado tem data de término.")
            new_completed = None

        if status_changed:
            fill_date = today or today_utc().isoformat()
            if new_status == "jogando" and started_at is UNSET and new_started is None:
                new_started = fill_date
            if new_status == "zerado" and completed_at is UNSET and new_completed is None:
                new_completed = fill_date

        if new_started and new_completed and new_completed < new_started:
            errors.add("completed_at", "A data de término não pode ser anterior à data de início.")
        errors.raise_if_any()

        if current is None:
            execute(
                "INSERT INTO library_entries"
                " (user_id, game_id, status, is_favorite, started_at, completed_at, status_changed_at,"
                "  created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, game_id, new_status, int(new_favorite), new_started, new_completed, now, now, now),
            )
            created = True
        else:
            execute(
                "UPDATE library_entries SET status = ?, is_favorite = ?, started_at = ?,"
                " completed_at = ?, status_changed_at = ?, updated_at = ? WHERE id = ?",
                (
                    new_status,
                    int(new_favorite),
                    new_started,
                    new_completed,
                    now if status_changed else (current["status_changed_at"] or current["updated_at"]),
                    now,
                    current["id"],
                ),
            )
        if status_changed:
            execute(
                "INSERT INTO activities (user_id, type, game_id, status, created_at)"
                " VALUES (?, 'logged', ?, ?, ?)",
                (user_id, game_id, new_status, now),
            )
    return get_entry(user_id, game_id), created  # type: ignore[return-value]


def delete_entry(user_id: int, game_id: int) -> dict | None:
    """Remove a entrada, as jogadas anteriores e o rastro delas no histórico.

    Nota e review só existem para um jogo que a pessoa jogou: sem o jogo no diário, elas saem junto (com as
    curtidas e a atividade "avaliou"). Devolve `{"review_removed": bool}`, ou None se o jogo não estava no diário.
    """
    with transaction():
        cursor = execute(
            "DELETE FROM library_entries WHERE user_id = ? AND game_id = ?", (user_id, game_id)
        )
        if cursor.rowcount == 0:
            return None
        execute("DELETE FROM playthroughs WHERE user_id = ? AND game_id = ?", (user_id, game_id))
        execute(
            "DELETE FROM activities WHERE user_id = ? AND game_id = ? AND type = 'logged'",
            (user_id, game_id),
        )
        removed = execute("DELETE FROM reviews WHERE user_id = ? AND game_id = ?", (user_id, game_id))
    return {"review_removed": removed.rowcount > 0}


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
                "Só dá para jogar de novo um jogo que você zerou ou abandonou. Para retomar um jogo pausado, volte para “Jogando”.",
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
