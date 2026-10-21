"""Jogar de novo: a jogada atual vai para o histórico do jogo e outra começa."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.utils.dates import today_utc

from .conftest import CELESTE, HADES


def put(client, rawg_id, **body):
    return client.put(f"/api/library/{rawg_id}", body)


def replay(client, rawg_id=HADES, **body):
    return client.post(f"/api/library/{rawg_id}/replay", body)


def finished(client, rawg_id=HADES, start="2025-03-01", end="2025-03-20"):
    return put(client, rawg_id, status="zerado", started_at=start, completed_at=end)


def test_a_new_entry_has_one_play_and_no_history(ana):
    entry = put(ana, HADES, status="jogando").get_json()["entry"]
    assert entry["plays"] == 1
    viewer = ana.get(f"/api/games/{HADES}").get_json()["viewer"]
    assert viewer["playthroughs"] == []


def test_replay_archives_the_current_play_and_starts_another(ana):
    finished(ana)
    put(ana, HADES, is_favorite=True)
    response = replay(ana)
    assert response.status_code == 201
    data = response.get_json()
    entry = data["entry"]
    assert entry["status"] == "jogando"
    assert entry["started_at"] == today_utc().isoformat() and entry["completed_at"] is None
    assert entry["is_favorite"] is True  # o favorito é do jogo, não da jogada
    assert entry["plays"] == 2
    [old] = data["playthroughs"]
    assert (old["status"], old["started_at"], old["completed_at"]) == ("zerado", "2025-03-01", "2025-03-20")
    assert data["game"]["name"] == "Hades"


def test_replay_uses_the_clients_local_date(ana):
    finished(ana)
    local_today = (today_utc() - timedelta(days=1)).isoformat()
    assert replay(ana, today=local_today).get_json()["entry"]["started_at"] == local_today


@pytest.mark.parametrize("bad", ["amanhã", "2026-13-40", 5, (today_utc() + timedelta(days=3)).isoformat()])
def test_replay_rejects_a_bad_client_date_and_changes_nothing(ana, bad):
    finished(ana)
    response = replay(ana, today=bad)
    assert response.status_code == 422 and "today" in response.get_json()["error"]["fields"]
    assert put(ana, HADES).get_json()["entry"]["plays"] == 1


@pytest.mark.parametrize("status", ["zerado", "abandonado", "pausado"])
def test_replay_is_allowed_after_finishing_dropping_or_pausing(ana, status):
    put(ana, HADES, status=status)
    data = replay(ana).get_json()
    assert [p["status"] for p in data["playthroughs"]] == [status]


@pytest.mark.parametrize("status", ["quero_jogar", "jogando"])
def test_replay_is_refused_while_the_game_is_not_played_or_is_being_played(ana, status):
    put(ana, HADES, status=status)
    response = replay(ana)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "cannot_replay"
    assert ana.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"] == []


def test_double_click_does_not_create_a_phantom_play(ana):
    finished(ana)
    assert replay(ana).status_code == 201
    assert replay(ana).status_code == 409  # já está jogando de novo
    assert len(ana.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"]) == 1


def test_replay_of_a_game_that_is_not_in_the_diary_is_a_404(ana):
    assert replay(ana, HADES).status_code == 404  # jogo desconhecido
    put(ana, CELESTE, status="zerado")
    assert replay(ana, HADES).status_code == 404  # jogo conhecido, mas fora do diário
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 7})  # a review cria a cópia local do jogo
    assert replay(ana, HADES).status_code == 404


def test_replay_requires_login_and_csrf(api, ana):
    finished(ana)
    assert api.post(f"/api/library/{HADES}/replay", {}).status_code == 401
    assert ana.post(f"/api/library/{HADES}/replay", {}, csrf=False).status_code == 403


def test_several_replays_keep_the_order_and_the_count(ana):
    finished(ana, start="2023-01-01", end="2023-01-30")
    replay(ana)
    put(ana, HADES, status="abandonado", started_at="2024-05-01")
    replay(ana)
    put(ana, HADES, status="zerado", started_at="2025-06-01", completed_at="2025-06-10")
    data = replay(ana).get_json()
    assert [(p["status"], p["started_at"]) for p in data["playthroughs"]] == [
        ("zerado", "2023-01-01"),
        ("abandonado", "2024-05-01"),
        ("zerado", "2025-06-01"),
    ]
    assert data["entry"]["plays"] == 4
    assert ana.get("/api/library").get_json()["items"][0]["entry"]["plays"] == 4
    assert ana.get("/api/users/ana/library").get_json()["counts"]["total"] == 1  # continua um jogo no diário


def test_the_rating_stays_single_per_game_across_plays(ana):
    finished(ana)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Ótimo."})
    replay(ana)
    assert ana.get("/api/library").get_json()["items"][0]["rating"] == 9
    assert ana.post(f"/api/games/{HADES}/reviews", {"rating": 5}).status_code == 409


def test_replay_shows_up_in_the_feed_as_a_replay(ana, bruno):
    bruno.put("/api/users/ana/follow")
    finished(ana)
    replay(ana)
    items = bruno.get("/api/feed").get_json()["items"]
    assert [(a["status"], a["replay"]) for a in items] == [("jogando", True), ("zerado", False)]
    # uma mudança comum de status não é um recomeço
    put(ana, HADES, status="pausado")
    put(ana, HADES, status="jogando")
    assert bruno.get("/api/feed").get_json()["items"][0]["replay"] is False


def test_delete_a_past_play(ana):
    finished(ana)
    replay(ana)
    [old] = ana.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"]
    response = ana.delete(f"/api/library/{HADES}/playthroughs/{old['id']}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["playthroughs"] == [] and data["entry"]["plays"] == 1
    assert data["entry"]["status"] == "jogando"  # a jogada atual não muda
    assert ana.delete(f"/api/library/{HADES}/playthroughs/{old['id']}").status_code == 404


def test_cannot_delete_other_peoples_plays_or_use_another_games_id(ana, bruno):
    finished(ana)
    replay(ana)
    finished(bruno, CELESTE)
    replay(bruno, CELESTE)
    [mine] = ana.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"]
    [his] = bruno.get(f"/api/games/{CELESTE}").get_json()["viewer"]["playthroughs"]
    assert bruno.delete(f"/api/library/{HADES}/playthroughs/{mine['id']}").status_code == 404
    assert ana.delete(f"/api/library/{CELESTE}/playthroughs/{mine['id']}").status_code == 404
    assert ana.delete(f"/api/library/{CELESTE}/playthroughs/{his['id']}").status_code == 404
    assert len(ana.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"]) == 1
    assert len(bruno.get(f"/api/games/{CELESTE}").get_json()["viewer"]["playthroughs"]) == 1


def test_removing_the_game_from_the_diary_removes_its_past_plays(ana, bruno, app):
    finished(ana)
    replay(ana)
    finished(bruno)
    replay(bruno)
    assert ana.delete(f"/api/library/{HADES}").status_code == 200
    from app import db as database

    raw = database.connect(app.config["DATABASE"])
    rows = raw.execute("SELECT user_id FROM playthroughs").fetchall()
    raw.close()
    assert [r["user_id"] for r in rows] == [bruno.user["id"]]  # só o histórico do outro permanece


def test_past_plays_are_only_visible_to_their_owner_in_the_game_page(ana, bruno):
    finished(ana)
    replay(ana)
    assert bruno.get(f"/api/games/{HADES}").get_json()["viewer"]["playthroughs"] == []
    assert "playthroughs" not in ana.get("/api/users/ana").get_json()


def test_profile_completions_count_past_plays_and_survive_a_replay(ana):
    year = today_utc().year
    put(ana, HADES, status="zerado", started_at=f"{year}-01-05", completed_at=f"{year}-02-10")
    before = ana.get("/api/users/ana").get_json()["stats"]
    assert before["completed_this_year"] == 1 and before["completions_by_month"][1] == 1

    replay(ana)  # recomeçar não pode apagar a conclusão que já aconteceu
    after_replay = ana.get("/api/users/ana").get_json()["stats"]
    assert after_replay["completed_this_year"] == 1 and after_replay["completions_by_month"][1] == 1
    assert after_replay["by_status"]["zerado"] == 0 and after_replay["by_status"]["jogando"] == 1
    assert after_replay["games"] == 1

    assert put(ana, HADES, status="zerado", started_at=f"{year}-03-01", completed_at=f"{year}-04-20").status_code == 200
    twice = ana.get("/api/users/ana").get_json()["stats"]
    assert twice["completed_this_year"] == 2  # zerou duas vezes no ano
    assert twice["completions_by_month"][1] == 1 and twice["completions_by_month"][3] == 1
    assert twice["games"] == 1


def test_past_abandoned_plays_do_not_count_as_completions(ana):
    year = today_utc().year
    put(ana, HADES, status="abandonado", started_at=f"{year}-01-05", completed_at=f"{year}-02-10")
    replay(ana)
    stats = ana.get("/api/users/ana").get_json()["stats"]
    assert stats["completed_this_year"] == 0 and sum(stats["completions_by_month"]) == 0
