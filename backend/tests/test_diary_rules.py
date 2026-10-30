"""O que cada status do diário permite: datas, favorito, nota e review, jogos ainda não lançados.

A ideia central: "Quero jogar" é um jogo que a pessoa ainda não começou. Data de início, favorito, nota e
review pertencem a quem já começou (jogando, pausado, abandonado ou zerado); a data de término só existe em
jogo zerado; e um jogo que ainda não saiu só fica em "Quero jogar".
"""
from __future__ import annotations

import random
import re
from datetime import date, timedelta

import pytest

from app import db as database
from app.services import rawg
from app.utils.dates import utcnow_iso

from . import fake_rawg
from .conftest import CELESTE, HADES, HOLLOW, UPCOMING

STARTED = ["jogando", "pausado", "abandonado", "zerado"]
TODAY = date.today()


def put(client, rawg_id, **body):
    return client.put(f"/api/library/{rawg_id}", body)


def entry(client, rawg_id=HADES):
    return client.get(f"/api/games/{rawg_id}").get_json()["viewer"]["entry"]


def rate(client, rawg_id=HADES, rating=8, **body):
    return client.post(f"/api/games/{rawg_id}/reviews", {"rating": rating, **body})


def error_of(response):
    return response.get_json()["error"]


def sql(app, query, params=()):
    connection = database.connect(app.config["DATABASE"])
    try:
        rows = connection.execute(query, params).fetchall()
        connection.commit()
        return rows
    finally:
        connection.close()


def kinds(client, username="ana"):
    return [i["type"] for i in client.get(f"/api/users/{username}/activity").get_json()["items"]]


# ----------------------------------------------------------------------------- "Quero jogar" não tem datas
@pytest.mark.parametrize("field", ["started_at", "completed_at"])
def test_a_game_on_the_wish_list_cannot_be_created_with_dates(ana, field):
    response = put(ana, HADES, status="quero_jogar", **{field: "2025-01-10"})
    assert response.status_code == 422
    assert field in error_of(response)["fields"]
    assert entry(ana) is None  # nada foi salvo
    assert kinds(ana) == []  # nem a atividade


@pytest.mark.parametrize("field", ["started_at", "completed_at"])
def test_a_game_on_the_wish_list_rejects_dates_later_too(ana, field):
    put(ana, HADES, status="quero_jogar")
    response = put(ana, HADES, **{field: "2025-01-10"})
    assert response.status_code == 422 and field in error_of(response)["fields"]
    assert entry(ana)["started_at"] is None and entry(ana)["completed_at"] is None


def test_the_wish_list_accepts_clearing_dates_and_ignores_nothing_silently(ana):
    put(ana, HADES, status="quero_jogar")
    assert put(ana, HADES, started_at=None, completed_at=None).status_code == 200  # limpar é sempre permitido


def test_changing_status_and_sending_a_date_the_new_status_refuses_is_an_error(ana):
    put(ana, HADES, status="quero_jogar")
    response = put(ana, HADES, status="jogando", completed_at="2025-01-10")
    assert response.status_code == 422 and "completed_at" in error_of(response)["fields"]
    assert entry(ana)["status"] == "quero_jogar"


# ----------------------------------------------------------------------------- data de término só em jogo zerado
@pytest.mark.parametrize("status", ["jogando", "pausado", "abandonado"])
def test_only_a_finished_game_has_a_completion_date(ana, status):
    response = put(ana, HADES, status=status, started_at="2025-01-10", completed_at="2025-02-10")
    assert response.status_code == 422
    assert error_of(response)["fields"] == {"completed_at": "Só um jogo zerado tem data de término."}
    assert entry(ana) is None
    assert put(ana, HADES, status=status, started_at="2025-01-10").status_code == 201


def test_a_finished_game_takes_both_dates(ana):
    data = put(ana, HADES, status="zerado", started_at="2025-01-10", completed_at="2025-02-10").get_json()["entry"]
    assert (data["started_at"], data["completed_at"]) == ("2025-01-10", "2025-02-10")


@pytest.mark.parametrize("status", ["jogando", "pausado", "abandonado"])
def test_leaving_finished_clears_the_completion_date_but_keeps_the_start(ana, status):
    put(ana, HADES, status="zerado", started_at="2025-01-10", completed_at="2025-02-10")
    data = put(ana, HADES, status=status).get_json()["entry"]
    assert data["status"] == status
    assert (data["started_at"], data["completed_at"]) == ("2025-01-10", None)


def test_finishing_again_fills_in_today_instead_of_a_stale_date(ana):
    put(ana, HADES, status="zerado", started_at="2025-01-10", completed_at="2025-02-10")
    put(ana, HADES, status="jogando")
    data = put(ana, HADES, status="zerado", today=TODAY.isoformat()).get_json()["entry"]
    assert data["completed_at"] == TODAY.isoformat()


def test_a_completion_date_before_the_start_is_still_refused(ana):
    response = put(ana, HADES, status="zerado", started_at="2025-03-10", completed_at="2025-02-10")
    assert response.status_code == 422 and "completed_at" in error_of(response)["fields"]


# ----------------------------------------------------------------------------- favorito
def test_the_wish_list_has_no_favorites(ana):
    created = put(ana, HADES, status="quero_jogar", is_favorite=True)
    assert created.status_code == 409 and error_of(created)["code"] == "cannot_favorite"
    assert entry(ana) is None
    put(ana, HADES, status="quero_jogar")
    again = put(ana, HADES, is_favorite=True)
    assert again.status_code == 409 and error_of(again)["code"] == "cannot_favorite"
    assert entry(ana)["is_favorite"] is False


@pytest.mark.parametrize("status", STARTED)
def test_a_started_game_can_be_a_favorite(ana, status):
    put(ana, HADES, status=status)
    assert put(ana, HADES, is_favorite=True).get_json()["entry"]["is_favorite"] is True


def test_going_back_to_the_wish_list_clears_dates_and_favorite(ana):
    put(ana, HADES, status="zerado", started_at="2025-01-10", completed_at="2025-02-10", is_favorite=True)
    data = put(ana, HADES, status="quero_jogar").get_json()["entry"]
    assert data["status"] == "quero_jogar"
    assert (data["started_at"], data["completed_at"], data["is_favorite"]) == (None, None, False)
    assert ana.get("/api/users/ana").get_json()["stats"]["favorites"] == 0


# ----------------------------------------------------------------------------- nota e review só de quem jogou
def test_you_cannot_rate_a_game_that_is_not_in_your_diary(ana):
    response = rate(ana)
    assert response.status_code == 409
    assert error_of(response)["code"] == "not_played"
    assert "diário" in error_of(response)["message"]
    assert ana.get(f"/api/games/{HADES}").get_json()["community"]["count"] == 0
    assert ana.get("/api/users/ana/reviews").get_json()["items"] == []


def test_you_cannot_rate_a_game_on_the_wish_list(ana):
    put(ana, HADES, status="quero_jogar")
    response = rate(ana, body="Parece bom.")
    assert response.status_code == 409 and error_of(response)["code"] == "not_played"
    assert "Quero jogar" in error_of(response)["message"]
    assert ana.get("/api/users/ana/reviews").get_json()["items"] == []
    assert "reviewed" not in kinds(ana)


@pytest.mark.parametrize("status", STARTED)
def test_whoever_started_the_game_can_rate_it(ana, status):
    put(ana, HADES, status=status)
    assert rate(ana, rating=9, body="Joguei.").status_code == 201


def test_a_rating_refused_for_the_wish_list_works_after_the_status_changes(ana):
    put(ana, HADES, status="quero_jogar")
    assert rate(ana).status_code == 409
    put(ana, HADES, status="jogando")
    assert rate(ana).status_code == 201


def test_rating_validation_comes_before_the_play_rule(ana):
    response = rate(ana, rating=11)  # nota inválida e jogo fora do diário: o erro de campo aparece
    assert response.status_code == 422 and "rating" in error_of(response)["fields"]


def test_a_game_with_a_rating_does_not_go_back_to_the_wish_list(ana):
    put(ana, HADES, status="zerado")
    rate(ana, rating=9)
    response = put(ana, HADES, status="quero_jogar")
    assert response.status_code == 409 and error_of(response)["code"] == "already_played"
    assert "avaliou" in error_of(response)["message"]
    assert entry(ana)["status"] == "zerado"
    assert ana.get(f"/api/games/{HADES}").get_json()["viewer"]["review"]["rating"] == 9


def test_deleting_the_rating_lets_the_game_go_back_to_the_wish_list(ana):
    put(ana, HADES, status="zerado")
    review_id = rate(ana).get_json()["review"]["id"]
    assert ana.delete(f"/api/reviews/{review_id}").status_code == 200
    assert put(ana, HADES, status="quero_jogar").status_code == 200


def test_a_game_with_earlier_plays_does_not_go_back_to_the_wish_list(ana):
    put(ana, HADES, status="zerado")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    response = put(ana, HADES, status="quero_jogar")
    assert response.status_code == 409 and error_of(response)["code"] == "already_played"
    assert entry(ana)["status"] == "jogando"


def test_a_played_game_without_rating_can_go_back_to_the_wish_list_and_it_is_logged(ana):
    put(ana, HADES, status="pausado")
    assert put(ana, HADES, status="quero_jogar").status_code == 200
    assert kinds(ana) == ["logged", "logged"]


def test_a_leftover_rating_blocks_creating_the_entry_as_wish_list(ana, app):
    """Reviews antigas de jogos fora do diário (de antes destas regras) continuam; o jogo só não vira "Quero jogar"."""
    put(ana, HADES, status="zerado")
    rate(ana)
    sql(app, "DELETE FROM library_entries")
    response = put(ana, HADES, status="quero_jogar")
    assert response.status_code == 409 and error_of(response)["code"] == "already_played"


def test_a_leftover_rating_can_still_be_edited_and_deleted(ana, app):
    put(ana, HADES, status="zerado")
    review_id = rate(ana).get_json()["review"]["id"]
    sql(app, "DELETE FROM library_entries")  # fica uma review sem registro no diário
    assert ana.patch(f"/api/reviews/{review_id}", {"rating": 6.5}).status_code == 200
    assert ana.delete(f"/api/reviews/{review_id}").status_code == 200


# ----------------------------------------------------------------------------- tirar do diário leva a nota junto
def test_removing_a_game_from_the_diary_takes_its_rating_review_and_likes(ana, bruno):
    put(ana, HADES, status="zerado")
    review_id = rate(ana, rating=9, body="Ótimo.").get_json()["review"]["id"]
    bruno.play(HADES)
    assert bruno.put(f"/api/reviews/{review_id}/like").status_code == 200

    response = ana.delete(f"/api/library/{HADES}", {"with_review": True})
    assert response.status_code == 200 and response.get_json() == {"ok": True, "review_removed": True}
    assert ana.get(f"/api/reviews/{review_id}").status_code == 404
    community = ana.get(f"/api/games/{HADES}").get_json()["community"]
    assert community["count"] == 0 and community["average"] is None
    assert kinds(ana) == []  # nem o "registrou" nem o "avaliou" sobraram
    assert ana.get("/api/users/ana").get_json()["stats"]["ratings"] == 0


def test_removing_a_game_with_a_rating_needs_the_confirmation_and_changes_nothing_without_it(ana):
    """Uma aba desatualizada (que não sabe da nota) não pode apagar a nota sem a pessoa ter visto o aviso."""
    put(ana, HADES, status="zerado")
    review_id = rate(ana, rating=9, body="Ótimo.").get_json()["review"]["id"]
    for body in (None, {}, {"with_review": False}, {"with_review": "true"}, {"with_review": 1}):
        response = ana.delete(f"/api/library/{HADES}", body)
        assert response.status_code == 409 and error_of(response)["code"] == "review_would_be_removed", body
        assert "nota" in error_of(response)["message"]
    assert entry(ana)["status"] == "zerado"
    assert ana.get(f"/api/reviews/{review_id}").status_code == 200
    assert kinds(ana) != []  # o histórico também ficou como estava


def test_removing_a_game_without_a_rating_says_there_was_none(ana):
    put(ana, HADES, status="jogando")
    assert ana.delete(f"/api/library/{HADES}").get_json() == {"ok": True, "review_removed": False}


def test_confirming_the_removal_of_a_rating_that_is_not_there_is_harmless(ana):
    put(ana, HADES, status="jogando")
    response = ana.delete(f"/api/library/{HADES}", {"with_review": True})
    assert response.status_code == 200 and response.get_json() == {"ok": True, "review_removed": False}


def test_removing_a_game_keeps_the_rating_of_other_games_and_of_other_people(ana, bruno):
    put(ana, HADES, status="zerado")
    put(ana, CELESTE, status="zerado")
    rate(ana, HADES)
    rate(ana, CELESTE, rating=7)
    bruno.play(HADES)
    rate(bruno, HADES, rating=5)
    ana.delete(f"/api/library/{HADES}", {"with_review": True})
    assert ana.get("/api/users/ana/reviews").get_json()["items"][0]["game"]["name"] == "Celeste"
    assert ana.get(f"/api/games/{HADES}").get_json()["community"]["count"] == 1  # a do bruno


# ----------------------------------------------------------------------------- jogo que ainda não saiu
def test_the_fake_game_really_is_not_released(ana):
    released = ana.get(f"/api/games/{UPCOMING}").get_json()["game"]["released"]
    assert released > TODAY.isoformat()


def test_an_unreleased_game_can_only_go_on_the_wish_list(ana):
    assert put(ana, UPCOMING, status="quero_jogar").status_code == 201


@pytest.mark.parametrize("status", STARTED)
def test_an_unreleased_game_cannot_be_played(ana, status):
    response = put(ana, UPCOMING, status=status)
    assert response.status_code == 409 and error_of(response)["code"] == "not_released"
    assert "só será lançado em" in error_of(response)["message"]
    assert entry(ana, UPCOMING) is None


def test_an_unreleased_game_on_the_wish_list_cannot_be_rated_or_started(ana):
    put(ana, UPCOMING, status="quero_jogar")
    rated = rate(ana, UPCOMING)
    assert rated.status_code == 409 and error_of(rated)["code"] == "not_released"
    assert put(ana, UPCOMING, status="jogando").status_code == 409
    assert put(ana, UPCOMING, is_favorite=True).status_code == 409
    assert entry(ana, UPCOMING)["status"] == "quero_jogar"


def test_once_the_game_comes_out_it_can_be_played_and_rated(ana, app):
    put(ana, UPCOMING, status="quero_jogar")
    sql(app, "UPDATE games SET release_date = ? WHERE rawg_id = ?", ((TODAY - timedelta(days=1)).isoformat(), UPCOMING))
    # a página do jogo traz a data da RAWG, que continua no futuro; ela só substitui a cópia local quando difere
    assert put(ana, UPCOMING, status="jogando").status_code == 200
    assert rate(ana, UPCOMING).status_code == 201


def test_a_game_without_a_known_release_date_is_not_blocked(ana, app):
    put(ana, HADES, status="quero_jogar")
    sql(app, "UPDATE games SET release_date = NULL WHERE rawg_id = ?", (HADES,))
    assert put(ana, HADES, status="jogando").status_code == 200


def test_the_release_day_uses_the_clients_today(ana, app):
    put(ana, HADES, status="quero_jogar")
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    sql(app, "UPDATE games SET release_date = ? WHERE rawg_id = ?", (tomorrow, HADES))
    # quem está no fuso em que já é "amanhã" pode jogar; quem está em "hoje" ainda não
    assert put(ana, HADES, status="jogando", today=TODAY.isoformat()).status_code == 409
    assert put(ana, HADES, status="jogando", today=tomorrow).status_code == 200


def test_rating_also_uses_the_clients_today_to_decide_if_the_game_is_out(ana, app):
    put(ana, HADES, status="jogando")
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    sql(app, "UPDATE games SET release_date = ? WHERE rawg_id = ?", (tomorrow, HADES))
    refused = rate(ana, today=TODAY.isoformat())
    assert refused.status_code == 409 and error_of(refused)["code"] == "not_released"
    assert rate(ana, today=tomorrow).status_code == 201  # no fuso em que o jogo já saiu, a nota vale


def test_rating_rejects_an_impossible_today(ana):
    put(ana, HADES, status="jogando")
    response = rate(ana, today=(TODAY + timedelta(days=30)).isoformat())
    assert response.status_code == 422 and "today" in error_of(response)["fields"]


def test_a_game_the_rawg_postpones_to_no_date_loses_the_old_local_date(ana, app, monkeypatch):
    """A RAWG pode tirar a data de um jogo (adiado, "a anunciar"): a cópia local acompanha, em vez de guardar a antiga."""
    put(ana, UPCOMING, status="quero_jogar")
    assert sql(app, "SELECT release_date FROM games WHERE rawg_id = ?", (UPCOMING,))[0][0] > TODAY.isoformat()
    original = fake_rawg.fetch_json

    def without_date(path, params=None):
        data = original(path, params)
        if path.strip("/") == f"games/{UPCOMING}":
            data = {**data, "released": None}
        return data

    monkeypatch.setattr(rawg, "fetch_json", without_date)
    rawg.clear_cache()
    ana.get(f"/api/games/{UPCOMING}")
    assert sql(app, "SELECT release_date FROM games WHERE rawg_id = ?", (UPCOMING,))[0][0] is None
    # sem data conhecida, ninguém é barrado por falta de dado (a mesma regra de qualquer jogo sem data)
    assert put(ana, UPCOMING, status="jogando").status_code == 200


def test_the_games_page_refreshes_a_stale_local_release_date(ana, app):
    put(ana, HADES, status="quero_jogar")
    sql(app, "UPDATE games SET release_date = ? WHERE rawg_id = ?", ((TODAY + timedelta(days=90)).isoformat(), HADES))
    assert put(ana, HADES, status="jogando").status_code == 409  # a cópia local diz que ainda vai sair
    ana.get(f"/api/games/{HADES}")  # abrir a página traz a data certa da RAWG (2020)
    assert sql(app, "SELECT release_date FROM games WHERE rawg_id = ?", (HADES,))[0][0] == "2020-09-17"
    assert put(ana, HADES, status="jogando").status_code == 200


# ----------------------------------------------------------------------------- jogar de novo
def test_a_paused_game_is_resumed_not_replayed(ana):
    put(ana, HADES, status="pausado", started_at="2025-01-10")
    response = ana.post(f"/api/library/{HADES}/replay", {})
    assert response.status_code == 409 and error_of(response)["code"] == "cannot_replay"
    assert "pausado" in error_of(response)["message"]
    resumed = put(ana, HADES, status="jogando").get_json()["entry"]
    assert resumed["started_at"] == "2025-01-10" and resumed["plays"] == 1  # a mesma jogada continua


@pytest.mark.parametrize(
    "status, fragment",
    [("quero_jogar", "na sua fila"), ("jogando", "já está jogando")],
)
def test_the_replay_refusal_explains_the_status_the_game_is_in(ana, status, fragment):
    put(ana, HADES, status=status)
    response = ana.post(f"/api/library/{HADES}/replay", {})
    assert response.status_code == 409 and error_of(response)["code"] == "cannot_replay"
    assert fragment in error_of(response)["message"]
    assert entry(ana)["status"] == status


def test_replaying_counts_as_a_status_change(ana, app):
    put(ana, HADES, status="zerado")
    sql(app, "UPDATE library_entries SET status_changed_at = '2020-01-01T10:00:00Z'")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    again = entry(ana)
    assert again["status"] == "jogando" and again["status_changed_at"] >= TODAY.isoformat()


# ----------------------------------------------------------------------------- "desde quando"
def test_status_changed_at_moves_with_the_status_and_not_with_other_edits(ana, app):
    put(ana, HADES, status="abandonado", started_at="2025-01-10")
    assert entry(ana)["status_changed_at"] >= TODAY.isoformat()
    sql(app, "UPDATE library_entries SET status_changed_at = '2020-01-01T10:00:00Z', updated_at = '2020-01-01T10:00:00Z'")
    put(ana, HADES, is_favorite=True)
    put(ana, HADES, started_at="2025-01-12")
    after_edits = entry(ana)
    assert after_edits["status_changed_at"] == "2020-01-01T10:00:00Z"  # favoritar e editar datas não mudam o status
    assert after_edits["updated_at"] > "2020-01-01T10:00:00Z"
    put(ana, HADES, status="pausado")
    assert entry(ana)["status_changed_at"] >= TODAY.isoformat()


# ----------------------------------------------------------------------------- a migração dos dados antigos
def test_migration_0003_cleans_old_entries_and_backfills_the_status_date(tmp_path, monkeypatch):
    old = tmp_path / "old-migrations"
    old.mkdir()
    for name in ("0001_initial.sql", "0002_jogadas_spoilers_foto_conta.sql"):
        (old / name).write_text((database.MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(database, "MIGRATIONS_DIR", old)
    path = tmp_path / "upgrade.db"
    assert len(database.migrate(path)) == 2

    raw = database.connect(path)
    user = raw.execute(
        "INSERT INTO users (username, display_name, email, password_hash, created_at, session_key)"
        " VALUES ('ana', 'Ana', 'ana@x.co', 'h', ?, 'k')",
        (utcnow_iso(),),
    ).lastrowid
    games = {}
    for number, status in enumerate(["quero_jogar", "jogando", "abandonado", "pausado", "zerado"]):
        games[status] = raw.execute(
            "INSERT INTO games (rawg_id, name, slug, created_at) VALUES (?, ?, ?, ?)",
            (7000 + number, f"Jogo {status}", f"jogo-{status}", utcnow_iso()),
        ).lastrowid
    rows = [
        ("quero_jogar", "2025-01-10", None, 1),  # início e favorito sem sentido
        ("jogando", "2025-01-10", "2025-03-01", 1),  # término sem sentido
        ("abandonado", "2025-01-10", "2025-03-01", 0),
        ("pausado", None, "2025-03-01", 0),
        ("zerado", "2025-01-10", "2025-03-01", 1),  # este está certo e não muda
    ]
    for status, started, completed, favorite in rows:
        raw.execute(
            "INSERT INTO library_entries (user_id, game_id, status, is_favorite, started_at, completed_at, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?, '2025-06-01T10:00:00Z', '2025-07-07T10:00:00Z')",
            (user, games[status], status, favorite, started, completed),
        )
    raw.execute(
        "INSERT INTO activities (user_id, type, game_id, status, created_at) VALUES (?, 'logged', ?, 'zerado', ?)",
        (user, games["zerado"], "2025-03-01T09:00:00Z"),
    )
    raw.execute(
        "INSERT INTO activities (user_id, type, game_id, status, created_at) VALUES (?, 'logged', ?, 'zerado', ?)",
        (user, games["zerado"], "2025-04-02T09:00:00Z"),
    )
    raw.execute(
        "INSERT INTO playthroughs (user_id, game_id, status, started_at, completed_at, created_at)"
        " VALUES (?, ?, 'abandonado', '2024-01-01', '2024-02-01', '2024-03-01T00:00:00Z')",
        (user, games["zerado"]),
    )
    raw.execute(
        "INSERT INTO playthroughs (user_id, game_id, status, started_at, completed_at, created_at)"
        " VALUES (?, ?, 'zerado', '2023-01-01', '2023-02-01', '2023-03-01T00:00:00Z')",
        (user, games["zerado"]),
    )
    raw.execute(
        "INSERT INTO reviews (user_id, game_id, rating, created_at) VALUES (?, ?, 9, '2025-02-02T00:00:00Z')",
        (user, games["quero_jogar"]),
    )
    raw.close()

    monkeypatch.undo()
    assert database.migrate(path) == ["0003_regras_do_diario"]

    raw = database.connect(path)
    try:
        got = {
            r["status"]: (r["started_at"], r["completed_at"], r["is_favorite"], r["status_changed_at"])
            for r in raw.execute("SELECT * FROM library_entries")
        }
        assert got["quero_jogar"] == (None, None, 0, "2025-07-07T10:00:00Z")  # sem atividade: cai em updated_at
        assert got["jogando"] == ("2025-01-10", None, 1, "2025-07-07T10:00:00Z")
        assert got["abandonado"] == ("2025-01-10", None, 0, "2025-07-07T10:00:00Z")
        assert got["pausado"] == (None, None, 0, "2025-07-07T10:00:00Z")
        assert got["zerado"] == ("2025-01-10", "2025-03-01", 1, "2025-04-02T09:00:00Z")  # a atividade mais recente
        plays = {r["status"]: r["completed_at"] for r in raw.execute("SELECT status, completed_at FROM playthroughs")}
        assert plays == {"abandonado": "2024-02-01", "zerado": "2023-02-01"}  # o passado não é reescrito
        assert raw.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1  # as notas antigas não são mexidas
    finally:
        raw.close()


# ----------------------------------------------------------------------------- front-end e servidor combinam
def test_the_front_end_rules_are_the_same_lists_as_the_servers():
    """frontend/src/utils/diary.js espelha as listas do servidor para só oferecer o que ele aceita."""
    from pathlib import Path

    from app.services import library

    source = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "diary.js").read_text(encoding="utf-8")

    def js_list(name):
        match = re.search(rf"export const {name} = \[([^\]]*)\];", source)
        assert match, f"{name} não foi encontrada em diary.js"
        return tuple(re.findall(r'"([a-z_]+)"', match.group(1)))

    assert js_list("STARTED") == library.STARTED
    assert js_list("COMPLETABLE") == library.COMPLETABLE
    assert js_list("REPLAYABLE") == library.REPLAYABLE


# ----------------------------------------------------------------------------- o conjunto nunca se contradiz
def _violations(app) -> list[str]:
    problems = []
    for row in sql(
        app,
        "SELECT e.status, e.is_favorite, e.started_at, e.completed_at, g.name,"
        " EXISTS (SELECT 1 FROM reviews r WHERE r.user_id = e.user_id AND r.game_id = e.game_id) AS rated,"
        " (SELECT COUNT(*) FROM playthroughs p WHERE p.user_id = e.user_id AND p.game_id = e.game_id) AS plays"
        " FROM library_entries e JOIN games g ON g.id = e.game_id",
    ):
        status, favorite, started, completed, name, rated, plays = tuple(row)
        label = f"{name}/{status}"
        if status == "quero_jogar" and (started or completed or favorite or rated or plays):
            problems.append(f"{label}: 'Quero jogar' com data, favorito, nota ou jogadas")
        if completed and status != "zerado":
            problems.append(f"{label}: data de término fora de um jogo zerado")
        if started and completed and completed < started:
            problems.append(f"{label}: término antes do início")
        if status != "quero_jogar" and name == "Farol do Amanhã":
            problems.append(f"{label}: jogo não lançado fora de 'Quero jogar'")
    for row in sql(
        app,
        "SELECT g.name FROM reviews r JOIN games g ON g.id = r.game_id WHERE NOT EXISTS ("
        " SELECT 1 FROM library_entries e WHERE e.user_id = r.user_id AND e.game_id = r.game_id"
        " AND e.status <> 'quero_jogar')",
    ):
        problems.append(f"{row[0]}: nota sem o jogo estar jogado no diário")
    return problems


def test_random_sequences_of_actions_never_break_the_rules(ana, bruno, app):
    """Mil ações aleatórias pela API (status, datas, favorito, nota, jogar de novo, remover): erro de regra é 4xx e o
    banco nunca guarda uma combinação sem sentido."""
    rng = random.Random(20261027)
    games = [HADES, CELESTE, HOLLOW, UPCOMING]
    statuses = ["quero_jogar", "jogando", "pausado", "abandonado", "zerado"]
    dates = [None, "2024-01-05", "2024-02-20", "2025-06-30", TODAY.isoformat()]
    served = 0
    for step in range(1000):
        client, game = rng.choice([ana, bruno]), rng.choice(games)
        action = rng.choice(["status", "status", "dates", "favorite", "rate", "rate", "replay", "remove", "unrate"])
        if action == "status":
            body = {"status": rng.choice(statuses)}
            if rng.random() < 0.4:
                body["started_at"] = rng.choice(dates)
            if rng.random() < 0.3:
                body["completed_at"] = rng.choice(dates)
            if rng.random() < 0.2:
                body["is_favorite"] = rng.random() < 0.5
            response = put(client, game, **body)
        elif action == "dates":
            response = put(client, game, started_at=rng.choice(dates), completed_at=rng.choice(dates))
        elif action == "favorite":
            response = put(client, game, is_favorite=rng.random() < 0.5)
        elif action == "rate":
            response = rate(client, game, rating=rng.choice([0, 3.5, 7, 10]))
        elif action == "unrate":
            current = client.get(f"/api/games/{game}").get_json()["viewer"]["review"]
            response = client.delete(f"/api/reviews/{current['id']}") if current else client.get("/api/health")
        elif action == "replay":
            response = client.post(f"/api/library/{game}/replay", {})
        else:
            response = client.delete(f"/api/library/{game}", {"with_review": rng.random() < 0.5})
        assert response.status_code < 500, (step, action, response.get_json())
        served += response.status_code < 400
        if step % 25 == 0:
            assert _violations(app) == [], (step, action)
    assert _violations(app) == []
    assert served > 300  # a maioria das ações do sorteio é válida: o teste não é só uma sequência de recusas
