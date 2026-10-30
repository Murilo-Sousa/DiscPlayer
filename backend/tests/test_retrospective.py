"""Retrospectiva do ano: contas e datas calculadas dos registros reais, sem inventar nada."""
from __future__ import annotations

import pytest

from app import create_app
from app import db as database
from app.services import rawg
from app.utils.dates import today_utc

from . import fake_rawg
from .conftest import CELESTE, HADES, HOLLOW, ZELDA, Api

BALATRO = fake_rawg.by_name("Balatro")["id"]
THIS_YEAR = today_utc().year


def url(username="ana", year=None):
    return f"/api/users/{username}/retrospective" + (f"/{year}" if year is not None else "")


def get(client, username="ana", year=None):
    response = client.get(url(username, year))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def put(client, rawg_id, **body):
    response = client.put(f"/api/library/{rawg_id}", body)
    assert response.status_code in (200, 201), response.get_json()
    return response


def finish(client, rawg_id, start, end):
    return put(client, rawg_id, status="zerado", started_at=start, completed_at=end)


def review(client, rawg_id, rating, body=None):
    payload = {"rating": rating}
    if body:
        payload["body"] = body
    client.play(rawg_id, status="pausado")  # só avalia quem já jogou; "pausado" não cria datas nem conclusões
    response = client.post(f"/api/games/{rawg_id}/reviews", payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["review"]["id"]


def sql(app, query, params=()):
    connection = database.connect(app.config["DATABASE"])
    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def backdate(app, table, stamp, where="1 = 1", params=()):
    sql(app, f"UPDATE {table} SET created_at = ? WHERE {where}", (stamp, *params))


# --------------------------------------------------------------------------- vazio e anos
def test_a_new_account_has_an_empty_retrospective_for_the_current_year(ana):
    data = get(ana)
    assert data["year"] == THIS_YEAR and data["partial"] is True and data["empty"] is True
    assert data["years"] == [] and data["game_of_the_year"] is None and data["pace"] is None
    assert data["totals"] == {"completed": 0, "completed_games": 0, "started": 0, "abandoned": 0, "replays": 0}
    assert data["by_month"] == [0] * 12 and data["busiest_month"] is None
    assert data["ratings"]["count"] == 0 and data["ratings"]["average"] is None


def test_it_is_public_and_shows_only_public_profile_data(ana, api):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    data = get(api, "ana", 2025)  # sem login
    assert data["user"] == {"username": "ana", "display_name": "ana", "avatar_url": None}
    assert "email" not in str(data) and "password" not in str(data) and "session_key" not in str(data)


def test_without_a_year_it_shows_the_latest_year_with_data(ana):
    finish(ana, HADES, "2024-03-01", "2024-03-20")
    finish(ana, CELESTE, "2022-05-01", "2022-05-10")
    data = get(ana)
    assert data["year"] == 2024 and data["partial"] is False
    assert data["years"] == [2024, 2022]


def test_years_list_merges_every_kind_of_record_newest_first(ana, app):
    finish(ana, HADES, "2021-03-01", "2021-03-20")  # término em 2021
    put(ana, CELESTE, status="jogando", started_at="2023-02-02")  # início em 2023
    review(ana, HOLLOW, 8)
    backdate(app, "reviews", "2020-06-01T12:00:00Z")  # review em 2020
    assert get(ana, year=2021)["years"] == [2023, 2021, 2020]


def test_a_year_with_only_an_abandoned_game_or_a_replay_shows_up(ana, app):
    put(ana, HADES, status="abandonado")  # só o histórico do diário
    backdate(app, "activities", "2018-05-05T12:00:00Z")
    assert get(ana)["years"][-1] == 2018
    put(ana, CELESTE, status="zerado")
    assert ana.post(f"/api/library/{CELESTE}/replay", {}).status_code == 201
    sql(app, "UPDATE activities SET created_at = '2019-07-07T12:00:00Z' WHERE is_replay = 1")
    sql(app, "UPDATE activities SET created_at = '2017-01-01T12:00:00Z' WHERE status = 'zerado' AND is_replay = 0")
    years = get(ana)["years"]
    assert 2019 in years and 2018 in years


def test_a_year_with_only_a_past_play_shows_up(ana, app):
    finish(ana, HOLLOW, "2016-03-01", "2016-03-20")
    assert ana.post(f"/api/library/{HOLLOW}/replay", {}).status_code == 201  # a jogada de 2016 vai para o histórico
    put(ana, HOLLOW, status="jogando", started_at="2022-02-02", completed_at=None)  # a atual é de outro ano
    sql(app, "UPDATE activities SET created_at = '2022-02-02T12:00:00Z'")  # nada do diário cai em 2016
    sql(app, "DELETE FROM reviews")
    years = get(ana)["years"]
    assert 2016 in years and 2022 in years


def test_a_year_with_only_a_past_play_end_date_shows_up(ana, app):
    finish(ana, HADES, "2015-01-01", "2015-02-01")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    sql(app, "UPDATE playthroughs SET started_at = NULL")  # só a data de término da jogada anterior
    sql(app, "UPDATE activities SET created_at = '2022-02-02T12:00:00Z'")
    put(ana, HADES, status="jogando", started_at="2022-02-02")
    assert 2015 in get(ana)["years"]


def test_a_year_with_only_a_past_play_start_date_shows_up(ana, app):
    finish(ana, HADES, "2014-12-20", "2015-01-05")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    sql(app, "UPDATE playthroughs SET completed_at = NULL")  # só a data de início da jogada anterior
    sql(app, "UPDATE activities SET created_at = '2022-02-02T12:00:00Z'")
    sql(app, "DELETE FROM reviews")
    put(ana, HADES, status="jogando", started_at="2022-02-02", completed_at=None)
    assert 2014 in get(ana)["years"]


def test_the_first_accepted_year_is_2000(ana):
    assert get(ana, year=2000)["empty"] is True
    assert ana.get(url(year=1999)).status_code == 404


def test_want_to_play_alone_does_not_create_a_year(ana):
    put(ana, HADES, status="quero_jogar")
    assert get(ana)["years"] == []


@pytest.mark.parametrize("year", [1999, 0, -5, THIS_YEAR + 2, 99999])
def test_years_out_of_range_are_not_found(ana, year):
    response = ana.get(url(year=year))
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "not_found"


def test_next_year_is_accepted_because_of_time_zones_ahead_of_utc(ana):
    assert get(ana, year=THIS_YEAR + 1)["empty"] is True


def test_a_non_numeric_year_and_an_unknown_user_are_not_found(ana):
    assert ana.get("/api/users/ana/retrospective/abc").status_code == 404
    assert ana.get("/api/users/ninguem/retrospective").status_code == 404
    assert ana.get("/api/users/ninguem/retrospective/2025").status_code == 404


# --------------------------------------------------------------------------- zerados
def test_completions_are_counted_by_the_end_date_with_inclusive_year_boundaries(ana):
    finish(ana, HADES, "2024-12-01", "2024-12-31")  # fora (ano anterior)
    finish(ana, CELESTE, "2024-12-20", "2025-01-01")  # dentro
    finish(ana, HOLLOW, "2025-06-01", "2025-12-31")  # dentro
    finish(ana, ZELDA, "2025-12-30", "2026-01-01")  # fora (ano seguinte)
    data = get(ana, year=2025)
    assert data["totals"]["completed"] == 2
    assert {item["game"]["name"] for item in data["completed_games"]} == {"Celeste", "Hollow Knight"}


def test_only_finished_games_count_as_completed(ana):
    put(ana, HADES, status="abandonado", started_at="2025-01-10")
    put(ana, CELESTE, status="pausado", started_at="2025-01-10")
    put(ana, HOLLOW, status="jogando", started_at="2025-01-10")
    data = get(ana, year=2025)
    assert data["totals"]["completed"] == 0 and data["totals"]["started"] == 3


def test_past_plays_count_and_finishing_twice_is_two_completions_of_one_game(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    put(ana, HADES, status="zerado", started_at="2025-07-01", completed_at="2025-08-01")
    data = get(ana, year=2025)
    assert data["totals"]["completed"] == 2 and data["totals"]["completed_games"] == 1
    [item] = data["completed_games"]
    assert item["times"] == 2 and item["completed_at"] == "2025-08-01"
    assert data["by_month"][2] == 1 and data["by_month"][7] == 1


def test_a_replay_in_another_year_keeps_the_old_completion_in_its_own_year(ana):
    finish(ana, HADES, "2024-03-01", "2024-03-20")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    assert get(ana, year=2024)["totals"]["completed"] == 1  # recomeçar não apaga a conclusão


def test_months_match_the_profile_chart_and_the_busiest_tie_goes_to_the_earliest(ana):
    finish(ana, HADES, "2025-05-01", "2025-05-10")
    finish(ana, CELESTE, "2025-02-01", "2025-02-10")
    finish(ana, HOLLOW, "2025-05-12", "2025-05-30")
    finish(ana, ZELDA, "2025-02-12", "2025-02-28")
    data = get(ana, year=2025)
    assert data["by_month"] == [0, 2, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0]
    assert sum(data["by_month"]) == data["totals"]["completed"]
    assert data["busiest_month"] == 2  # fevereiro (empate com maio: vale o mais cedo)


def test_the_current_year_matches_the_profile_numbers(ana):
    today = today_utc().isoformat()
    finish(ana, HADES, today, today)
    data = get(ana, year=THIS_YEAR)
    stats = ana.get("/api/users/ana").get_json()["stats"]
    assert data["by_month"] == stats["completions_by_month"]
    assert data["totals"]["completed"] == stats["completed_this_year"] == 1


def test_completed_games_are_listed_best_rated_first_and_capped(ana):
    names = [g for g in fake_rawg.GAMES if g["id"] not in (HADES,)][:13]
    finish(ana, HADES, "2025-01-01", "2025-01-02")
    review(ana, HADES, 10)
    for index, game in enumerate(names):
        finish(ana, game["id"], "2025-02-01", f"2025-03-{index + 1:02d}")
    data = get(ana, year=2025)
    assert data["totals"]["completed"] == 14 and len(data["completed_games"]) == 12
    assert data["completed_games"][0]["game"]["name"] == "Hades"


# --------------------------------------------------------------------------- jogo do ano
def test_game_of_the_year_is_the_best_rated_among_the_years_completions(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    finish(ana, HOLLOW, "2025-04-01", "2025-04-20")
    finish(ana, CELESTE, "2024-04-01", "2024-04-20")
    review(ana, HADES, 9)
    review(ana, HOLLOW, 8)
    review(ana, CELESTE, 10)  # nota maior, mas zerado em outro ano
    review(ana, ZELDA, 10)  # nota maior, mas nunca zerado
    best = get(ana, year=2025)["game_of_the_year"]
    assert best["game"]["name"] == "Hades" and best["rating"] == 9
    assert get(ana, year=2024)["game_of_the_year"]["game"]["name"] == "Celeste"


def test_a_tie_goes_to_the_most_recent_completion(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    finish(ana, HOLLOW, "2025-04-01", "2025-09-20")
    review(ana, HADES, 9)
    review(ana, HOLLOW, 9)
    assert get(ana, year=2025)["game_of_the_year"]["game"]["name"] == "Hollow Knight"


def test_there_is_no_game_of_the_year_without_any_rating(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    data = get(ana, year=2025)
    assert data["game_of_the_year"] is None and data["completed_games"][0]["rating"] is None


def test_a_zero_rating_never_makes_a_game_of_the_year(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    review(ana, HADES, 0)
    data = get(ana, year=2025)
    assert data["game_of_the_year"] is None
    assert data["completed_games"][0]["rating"] == 0  # a nota 0 continua aparecendo na lista
    finish(ana, CELESTE, "2025-04-01", "2025-04-02")
    review(ana, CELESTE, 0.5)
    assert get(ana, year=2025)["game_of_the_year"]["game"]["name"] == "Celeste"


def test_the_rating_comes_from_the_review_whenever_it_was_written(ana, app):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    review(ana, HADES, 7.5)
    backdate(app, "reviews", "2023-01-01T00:00:00Z")  # review de outro ano
    assert get(ana, year=2025)["game_of_the_year"]["rating"] == 7.5


# --------------------------------------------------------------------------- ritmo
def test_pace_needs_two_completions_with_both_dates(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    assert get(ana, year=2025)["pace"] is None  # com um só, mais rápido e mais longo seriam o mesmo
    put(ana, CELESTE, status="zerado", completed_at="2025-04-01")  # sem data de início
    assert get(ana, year=2025)["pace"] is None


def test_pace_finds_the_fastest_the_longest_and_the_average(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-11")  # 10 dias
    finish(ana, CELESTE, "2025-04-05", "2025-04-05")  # no mesmo dia: 0
    finish(ana, HOLLOW, "2025-05-01", "2025-05-31")  # 30 dias
    pace = get(ana, year=2025)["pace"]
    assert pace["fastest"]["game"]["name"] == "Celeste" and pace["fastest"]["days"] == 0
    assert pace["longest"]["game"]["name"] == "Hollow Knight" and pace["longest"]["days"] == 30
    assert pace["average_days"] == pytest.approx(13.3, abs=0.05)


def test_the_item_days_use_the_latest_completion_of_the_game(ana):
    finish(ana, HADES, "2025-01-01", "2025-01-11")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    put(ana, HADES, status="zerado", started_at="2025-06-01", completed_at="2025-06-04")
    [item] = get(ana, year=2025)["completed_games"]
    assert item["days"] == 3


# --------------------------------------------------------------------------- começados, abandonados, recomeços
def test_started_counts_current_and_past_plays_by_the_start_date(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    assert ana.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    put(ana, HADES, started_at="2025-09-01")  # o recomeço começa em hoje; aqui ajustamos a data
    put(ana, CELESTE, status="jogando", started_at="2025-12-31")
    put(ana, HOLLOW, status="jogando", started_at="2024-12-31")
    assert get(ana, year=2025)["totals"]["started"] == 3  # Hades (2x) + Celeste


def test_abandoned_and_replays_come_from_the_diary_history_of_that_year(ana, app):
    put(ana, HADES, status="abandonado")
    put(ana, CELESTE, status="abandonado")
    put(ana, CELESTE, status="jogando")
    put(ana, CELESTE, status="abandonado")  # o mesmo jogo duas vezes conta uma
    put(ana, HOLLOW, status="zerado")
    assert ana.post(f"/api/library/{HOLLOW}/replay", {}).status_code == 201
    backdate(app, "activities", "2025-06-15T12:00:00Z")
    data = get(ana, year=2025)
    assert data["totals"]["abandoned"] == 2 and data["totals"]["replays"] == 1
    other = get(ana, year=2024)
    assert other["totals"]["abandoned"] == 0 and other["totals"]["replays"] == 0


def test_activity_at_the_year_boundary_follows_utc(ana, app):
    put(ana, HADES, status="abandonado")
    backdate(app, "activities", "2025-01-01T00:00:00Z")
    assert get(ana, year=2025)["totals"]["abandoned"] == 1
    backdate(app, "activities", "2024-12-31T23:59:59Z")
    assert get(ana, year=2025)["totals"]["abandoned"] == 0
    assert get(ana, year=2024)["totals"]["abandoned"] == 1


# --------------------------------------------------------------------------- notas
def test_ratings_count_only_reviews_published_in_the_year(ana, app):
    review(ana, HADES, 9, "ótimo")
    review(ana, CELESTE, 7)
    review(ana, HOLLOW, 4.5, "mais ou menos")
    backdate(app, "reviews", "2025-06-01T12:00:00Z", "rating >= 7")
    backdate(app, "reviews", "2024-06-01T12:00:00Z", "rating < 7")
    ratings = get(ana, year=2025)["ratings"]
    assert ratings["count"] == 2 and ratings["average"] == 8.0 and ratings["with_text"] == 1
    assert ratings["distribution"] == [0, 0, 0, 0, 0, 0, 0, 1, 0, 1]
    assert get(ana, year=2024)["ratings"]["distribution"][4] == 1


def test_a_ten_goes_into_the_last_bucket(ana, app):
    review(ana, HADES, 10)
    backdate(app, "reviews", "2025-06-01T12:00:00Z")
    assert get(ana, year=2025)["ratings"]["distribution"][9] == 1


def test_only_ratings_make_a_year_non_empty(ana, app):
    review(ana, HADES, 6)
    backdate(app, "reviews", "2025-06-01T12:00:00Z")
    data = get(ana, year=2025)
    assert data["empty"] is False and data["totals"]["completed"] == 0


# --------------------------------------------------------------------------- social
def test_social_numbers_use_the_year_the_event_happened(ana, bruno, app):
    review_id = review(ana, HADES, 9, "bom")
    assert bruno.put(f"/api/reviews/{review_id}/like").status_code == 200
    assert bruno.put("/api/users/ana/follow").status_code == 200
    backdate(app, "review_likes", "2025-02-02T10:00:00Z")
    backdate(app, "follows", "2025-03-03T10:00:00Z")
    social = get(ana, year=2025)["social"]
    assert social["likes_received"] == 1 and social["new_followers"] == 1
    assert get(ana, year=2024)["social"] == {"likes_received": 0, "new_followers": 0, "lists_created": 0}


def test_lists_created_counts_public_lists_only(ana, app):
    assert ana.post("/api/lists", {"title": "Pública", "is_public": True}).status_code == 201
    assert ana.post("/api/lists", {"title": "Segredo", "is_public": False}).status_code == 201
    backdate(app, "lists", "2025-04-04T10:00:00Z")
    assert get(ana, year=2025)["social"]["lists_created"] == 1


def test_nothing_of_a_private_list_or_review_text_appears(ana, bruno, app):
    ana.post("/api/lists", {"title": "Minha lista secreta", "description": "só eu vejo", "is_public": False})
    review(ana, HADES, 9, "No final o vilão era o mentor.")
    backdate(app, "lists", "2025-04-04T10:00:00Z")
    backdate(app, "reviews", "2025-04-04T10:00:00Z")
    text = str(get(bruno, "ana", 2025))
    assert "secreta" not in text and "só eu vejo" not in text and "vilão" not in text


def test_other_peoples_records_never_leak_in(ana, bruno):
    finish(bruno, HADES, "2025-03-01", "2025-03-20")
    review(bruno, HADES, 10)
    data = get(ana, year=2025)
    assert data["empty"] is True and data["completed_games"] == []
    assert get(bruno, "bruno", 2025)["totals"]["completed"] == 1


def test_deleting_the_diary_entry_removes_it_from_the_retrospective(ana):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    assert ana.delete(f"/api/library/{HADES}").status_code == 200
    assert get(ana, year=2025)["totals"]["completed"] == 0


# --------------------------------------------------------------------------- limite de requisições
def test_the_retrospective_is_rate_limited(tmp_path, monkeypatch):
    from app.security import reset_rate_limits

    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    reset_rate_limits()
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "limite.db"),
            "RATELIMIT_ENABLED": True,
            "RAWG_API_KEY": "chave-de-teste",
            "FRONTEND_DIST": str(tmp_path / "sem-dist"),
        }
    )
    client = Api(app)
    client.register("ana")
    codes = [client.get(url(year=2025)).status_code for _ in range(70)]
    assert codes[:60] == [200] * 60 and 429 in codes[60:]
