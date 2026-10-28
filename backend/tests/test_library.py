"""Diário pessoal: uma entrada por jogo, status, datas, favoritos e histórico."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import rawg
from app.utils.dates import today_utc

from . import fake_rawg
from .conftest import CELESTE, HADES, HOLLOW


def put(client, rawg_id, **body):
    return client.put(f"/api/library/{rawg_id}", body)


def test_log_a_game_creates_entry_with_server_side_metadata(ana):
    response = put(ana, HADES, status="quero_jogar")
    assert response.status_code == 201
    body = response.get_json()
    assert body["entry"]["status"] == "quero_jogar"
    assert body["entry"]["is_favorite"] is False
    assert body["game"]["name"] == "Hades"  # nome e capa vêm da RAWG, não do cliente
    assert body["game"]["cover_url"].startswith("https://media.rawg.io/")


def test_client_cannot_inject_game_metadata(ana):
    response = put(ana, HADES, status="jogando", name="Jogo Falso", cover_url="https://evil.example/x.png")
    assert response.get_json()["game"]["name"] == "Hades"


def test_logging_the_same_game_updates_instead_of_duplicating(ana):
    assert put(ana, HADES, status="jogando").status_code == 201
    second = put(ana, HADES, status="zerado")
    assert second.status_code == 200
    library = ana.get("/api/library").get_json()
    assert library["counts"]["total"] == 1
    assert library["items"][0]["entry"]["status"] == "zerado"


def test_partial_updates_keep_other_fields(ana):
    put(ana, HADES, status="jogando", started_at="2026-01-10")
    put(ana, HADES, is_favorite=True)
    entry = ana.get("/api/library").get_json()["items"][0]["entry"]
    assert entry["status"] == "jogando"
    assert entry["started_at"] == "2026-01-10"
    assert entry["is_favorite"] is True


def test_status_is_required_when_creating(ana):
    response = put(ana, HADES, is_favorite=True)
    assert response.status_code == 422
    assert "status" in response.get_json()["error"]["fields"]
    assert ana.get("/api/library").get_json()["counts"]["total"] == 0


@pytest.mark.parametrize("status", ["terminado", "", None, 3, "JOGANDO"])
def test_invalid_status_is_rejected(ana, status):
    assert put(ana, HADES, status=status).status_code == 422


def test_all_five_statuses_are_accepted(ana):
    games = [fake_rawg.GAMES[i]["id"] for i in range(5)]
    for rawg_id, status in zip(games, ["quero_jogar", "jogando", "zerado", "abandonado", "pausado"]):
        assert put(ana, rawg_id, status=status).status_code == 201
    counts = ana.get("/api/library").get_json()["counts"]
    assert counts["total"] == 5
    assert all(counts[s] == 1 for s in ["quero_jogar", "jogando", "zerado", "abandonado", "pausado"])


def test_dates_are_filled_automatically_but_the_client_can_override(ana):
    today = today_utc().isoformat()  # sem `today` do cliente, o servidor usa a data UTC
    playing = put(ana, HADES, status="jogando").get_json()["entry"]
    assert playing["started_at"] == today and playing["completed_at"] is None

    done = put(ana, CELESTE, status="zerado", completed_at="2025-12-31").get_json()["entry"]
    assert done["completed_at"] == "2025-12-31"

    finished = put(ana, HADES, status="zerado").get_json()["entry"]
    assert finished["completed_at"] == today
    assert finished["started_at"] == today  # a data de início anterior foi preservada


@pytest.mark.parametrize(
    "body, field",
    [
        ({"started_at": "10/01/2026"}, "started_at"),
        ({"started_at": "2026-13-45"}, "started_at"),
        ({"started_at": "1969-12-31"}, "started_at"),
        ({"completed_at": (date.today() + timedelta(days=30)).isoformat()}, "completed_at"),
        ({"started_at": "2026-05-10", "completed_at": "2026-05-09"}, "completed_at"),
        ({"is_favorite": "sim"}, "is_favorite"),
    ],
)
def test_invalid_dates_and_flags_are_rejected(ana, body, field):
    response = put(ana, HADES, status="zerado", **body)
    assert response.status_code == 422
    assert field in response.get_json()["error"]["fields"]


def test_dates_can_be_cleared_with_null(ana):
    put(ana, HADES, status="jogando", started_at="2026-02-01")
    entry = put(ana, HADES, started_at=None).get_json()["entry"]
    assert entry["started_at"] is None


def test_status_changes_are_recorded_in_the_history_without_duplicating_the_entry(ana):
    for status in ["jogando", "zerado", "jogando", "zerado"]:
        put(ana, HADES, status=status)
    put(ana, HADES, status="zerado")  # mesmo status: nada novo no histórico
    activity = ana.get("/api/users/ana/activity").get_json()["items"]
    assert [a["status"] for a in activity] == ["zerado", "jogando", "zerado", "jogando"]
    assert ana.get("/api/library").get_json()["counts"]["total"] == 1


def test_list_filters_sorting_and_pagination(ana):
    ids = [fake_rawg.GAMES[i]["id"] for i in range(6)]
    for rawg_id in ids[:4]:
        put(ana, rawg_id, status="zerado")
    for rawg_id in ids[4:]:
        put(ana, rawg_id, status="jogando")
    only_playing = ana.get("/api/library?status=jogando").get_json()
    assert len(only_playing["items"]) == 2
    assert only_playing["counts"]["total"] == 6  # as contagens ignoram o filtro

    page = ana.get("/api/library?per_page=4&page=1").get_json()
    assert len(page["items"]) == 4 and page["has_next"] is True
    last = ana.get("/api/library?per_page=4&page=2").get_json()
    assert len(last["items"]) == 2 and last["has_next"] is False

    by_name = [i["game"]["name"] for i in ana.get("/api/library?sort=name").get_json()["items"]]
    assert by_name == sorted(by_name, key=str.lower)


def test_filter_favorites(ana):
    put(ana, HADES, status="zerado", is_favorite=True)
    put(ana, CELESTE, status="zerado")
    favorites = ana.get("/api/library?favorites=1").get_json()["items"]
    assert [i["game"]["name"] for i in favorites] == ["Hades"]


@pytest.mark.parametrize("query", ["status=nada", "sort=nada", "page=0", "per_page=9999", "page=abc"])
def test_invalid_listing_parameters_are_rejected(ana, query):
    assert ana.get(f"/api/library?{query}").status_code == 400


def test_remove_entry_and_its_history(ana):
    put(ana, HADES, status="zerado")
    assert ana.delete(f"/api/library/{HADES}").status_code == 200
    assert ana.get("/api/library").get_json()["counts"]["total"] == 0
    assert ana.get("/api/users/ana/activity").get_json()["items"] == []
    assert ana.delete(f"/api/library/{HADES}").status_code == 404


def test_users_only_touch_their_own_library(ana, bruno):
    put(ana, HADES, status="zerado", is_favorite=True)
    put(bruno, HADES, status="abandonado")
    assert ana.get("/api/library").get_json()["items"][0]["entry"]["status"] == "zerado"
    assert bruno.get("/api/library").get_json()["items"][0]["entry"]["status"] == "abandonado"
    bruno.delete(f"/api/library/{HADES}")
    assert ana.get("/api/library").get_json()["counts"]["total"] == 1


def test_unknown_game_is_a_404_and_nothing_is_saved(ana):
    response = put(ana, 123456789, status="jogando")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "game_not_found"
    assert ana.get("/api/library").get_json()["counts"]["total"] == 0


def test_rawg_outage_blocks_new_games_but_not_games_already_saved(ana, monkeypatch):
    put(ana, HADES, status="jogando")  # Hades passa a existir no banco local

    def down(*_a, **_k):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    rawg.clear_cache()

    assert put(ana, HADES, status="zerado").status_code == 200  # não precisa da RAWG
    blocked = put(ana, HOLLOW, status="jogando")
    assert blocked.status_code == 503
    assert blocked.get_json()["error"]["code"] == "rawg_unavailable"
    assert ana.get("/api/library").get_json()["counts"]["total"] == 1


def test_another_users_library_is_public_but_has_no_private_data(ana, bruno):
    put(ana, HADES, status="zerado")
    body = bruno.get("/api/users/ana/library").get_json()
    assert body["items"][0]["game"]["name"] == "Hades"
    assert "email" not in str(body)


def test_library_entries_carry_the_users_rating(ana):
    put(ana, HADES, status="zerado")
    assert ana.get("/api/library").get_json()["items"][0]["rating"] is None
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9.5})
    assert ana.get("/api/library").get_json()["items"][0]["rating"] == 9.5


def test_client_today_is_used_for_automatic_dates(ana):
    # Às 22h no Brasil já é "amanhã" em UTC: a data automática deve ser a do fuso de quem joga.
    local_today = (today_utc() - timedelta(days=1)).isoformat()
    playing = put(ana, HADES, status="jogando", today=local_today).get_json()["entry"]
    assert playing["started_at"] == local_today

    done = put(ana, HADES, status="zerado", today=local_today).get_json()["entry"]
    assert done["completed_at"] == local_today and done["started_at"] == local_today

    # Datas escolhidas pela pessoa continuam valendo mais do que o "hoje" informado.
    other = put(ana, CELESTE, status="zerado", completed_at="2025-12-31", today=local_today).get_json()["entry"]
    assert other["completed_at"] == "2025-12-31"


def test_client_today_one_day_ahead_is_accepted(ana):
    # Fusos adiantados (por exemplo, Nova Zelândia) estão um dia à frente de UTC.
    ahead = (today_utc() + timedelta(days=1)).isoformat()
    assert put(ana, HADES, status="jogando", today=ahead).get_json()["entry"]["started_at"] == ahead


@pytest.mark.parametrize("offset_days", [-2, 2, 400])
def test_client_today_far_from_utc_is_rejected(ana, offset_days):
    bad = (today_utc() + timedelta(days=offset_days)).isoformat()
    response = put(ana, HADES, status="jogando", today=bad)
    assert response.status_code == 422
    assert "today" in response.get_json()["error"]["fields"]


@pytest.mark.parametrize("bad", ["amanhã", "2026-13-40", "", 5, ["2026-10-19"]])
def test_client_today_with_bad_format_is_rejected(ana, bad):
    response = put(ana, HADES, status="jogando", today=bad)
    assert response.status_code == 422
    assert "today" in response.get_json()["error"]["fields"]
