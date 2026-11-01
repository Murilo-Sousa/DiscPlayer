"""O que a repaginada dos jogos acrescentou ao back-end: média da comunidade nas listas, status do diário por lista
de jogos, "mais do mesmo gênero" e o atalho de guardar na fila sem mexer em jogo que já está no diário."""
from __future__ import annotations

import pytest

from app.services import rawg

from . import fake_rawg
from .conftest import CELESTE, HADES, HOLLOW


def by_id(items, rawg_id):
    return next(item for item in items if item["rawg_id"] == rawg_id)


# ----------------------------------------------------------------------------- média da comunidade nas listas
def test_games_without_reviews_have_no_community_average(api):
    for game in api.get("/api/games?per_page=40").get_json()["results"]:
        assert game["community"] is None


def test_catalog_and_featured_carry_the_community_average_with_the_number_of_notes(ana, bruno):
    ana.play(HADES)
    bruno.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 8})
    catalog = ana.get("/api/games?per_page=40").get_json()["results"]
    assert by_id(catalog, HADES)["community"] == {"average": 8.5, "count": 2}
    assert by_id(catalog, CELESTE)["community"] is None
    featured = ana.get("/api/games/featured").get_json()
    shown = [game for game in featured["popular"] + featured["new"] if game["rawg_id"] == HADES]
    assert all(game["community"] == {"average": 8.5, "count": 2} for game in shown)


def test_the_cached_rawg_list_is_not_changed_by_adding_the_community_average(ana):
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    ana.get("/api/games?per_page=40")
    cached = rawg.search_games(ordering="popular", page_size=40)["results"]
    assert cached and all("community" not in game for game in cached)  # a nota nunca fica presa no cache da RAWG


def test_a_new_review_shows_up_in_the_next_catalog_request(ana, bruno):
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 10})
    assert by_id(ana.get("/api/games?per_page=40").get_json()["results"], HADES)["community"] == {"average": 10, "count": 1}
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 6})
    assert by_id(ana.get("/api/games?per_page=40").get_json()["results"], HADES)["community"] == {"average": 8, "count": 2}


# ----------------------------------------------------------------------------- status do diário por lista de jogos
def test_status_lookup_needs_a_login(api):
    response = api.get(f"/api/library/status?ids={HADES}")
    assert response.status_code == 401


def test_status_lookup_returns_only_the_games_in_the_callers_diary(ana, bruno):
    ana.put(f"/api/library/{HADES}", {"status": "zerado"})
    ana.put(f"/api/library/{CELESTE}", {"status": "quero_jogar"})
    ana.put(f"/api/library/{CELESTE}", {"is_favorite": False})
    bruno.put(f"/api/library/{HOLLOW}", {"status": "jogando"})
    ana.put(f"/api/library/{HADES}", {"is_favorite": True})
    items = ana.get(f"/api/library/status?ids={HADES},{CELESTE},{HOLLOW},999999").get_json()["items"]
    assert items == {
        str(HADES): {"status": "zerado", "is_favorite": True},
        str(CELESTE): {"status": "quero_jogar", "is_favorite": False},
    }  # o jogo do Bruno e o que ninguém tem ficam de fora
    assert bruno.get(f"/api/library/status?ids={HADES},{HOLLOW}").get_json()["items"] == {
        str(HOLLOW): {"status": "jogando", "is_favorite": False}
    }


def test_status_lookup_without_ids_is_empty_and_bad_ids_are_refused(ana):
    assert ana.get("/api/library/status").get_json() == {"items": {}}
    assert ana.get("/api/library/status?ids=").get_json() == {"items": {}}
    for bad in ("abc", "1,,2", "1,a", "-3", "1;2"):
        response = ana.get(f"/api/library/status?ids={bad}")
        assert response.status_code == 400, bad
        assert response.get_json()["error"]["code"] == "invalid_parameter"
    too_many = ",".join(str(number) for number in range(1, 82))
    assert ana.get(f"/api/library/status?ids={too_many}").status_code == 400
    assert ana.get("/api/library/status?ids=" + ",".join(str(n) for n in range(1, 81))).status_code == 200


# ----------------------------------------------------------------------------- guardar na fila só se for novo
def test_create_only_adds_a_new_game_to_the_queue(ana):
    response = ana.put(f"/api/library/{HADES}", {"status": "quero_jogar", "create_only": True})
    assert response.status_code == 201
    assert response.get_json()["entry"]["status"] == "quero_jogar"


def test_create_only_never_changes_a_game_that_is_already_in_the_diary(ana):
    ana.put(f"/api/library/{HADES}", {"status": "jogando"})
    before = ana.get(f"/api/games/{HADES}").get_json()["viewer"]["entry"]
    response = ana.put(f"/api/library/{HADES}", {"status": "quero_jogar", "create_only": True})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "already_in_diary"
    assert ana.get(f"/api/games/{HADES}").get_json()["viewer"]["entry"] == before  # nada mudou, nem a data do status


def test_without_create_only_the_same_request_still_updates(ana):
    ana.put(f"/api/library/{HADES}", {"status": "jogando"})
    response = ana.put(f"/api/library/{HADES}", {"status": "pausado"})
    assert response.status_code == 200 and response.get_json()["entry"]["status"] == "pausado"


def test_create_only_follows_the_diary_rules_for_a_game_that_is_not_out_yet(ana):
    upcoming = fake_rawg.by_name("Farol do Amanhã")["id"] if "Farol do Amanhã" in {g["name"] for g in fake_rawg.GAMES} else None
    if upcoming is None:
        pytest.skip("a RAWG de teste não tem esse jogo")
    # um jogo que ainda não saiu pode ir para a fila, que é exatamente o que o atalho faz
    assert ana.put(f"/api/library/{upcoming}", {"status": "quero_jogar", "create_only": True}).status_code == 201


# ----------------------------------------------------------------------------- mais do mesmo gênero
def test_related_games_share_the_first_genre_and_leave_out_the_game_itself(api):
    detail = api.get(f"/api/games/{HADES}").get_json()["game"]
    body = api.get(f"/api/games/{HADES}/related").get_json()
    assert body["genre"]["name"] == detail["genres"][0]
    assert body["genre"]["slug"]
    assert 0 < len(body["items"]) <= 12
    assert all(item["rawg_id"] != HADES for item in body["items"])
    assert all(body["genre"]["name"] in item["genres"] for item in body["items"])
    assert all("community" in item for item in body["items"])


def test_related_games_carry_the_community_average(ana):
    other = next(
        item["rawg_id"] for item in ana.get(f"/api/games/{HADES}/related").get_json()["items"] if item["rawg_id"] != HADES
    )
    ana.play(other)
    ana.post(f"/api/games/{other}/reviews", {"rating": 7})
    items = ana.get(f"/api/games/{HADES}/related").get_json()["items"]
    assert by_id(items, other)["community"] == {"average": 7, "count": 1}


def test_related_games_of_an_unknown_game_is_404(api):
    assert api.get("/api/games/99999999/related").status_code == 404


def test_related_games_become_an_empty_list_when_the_rawg_fails(api, monkeypatch):
    api.get(f"/api/games/{HADES}")  # o jogo já está no cache: o que falha é a busca pelo gênero

    def only_the_detail(path, params=None):
        if path == "games":
            raise rawg.RawgUnavailable()
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", only_the_detail)
    rawg.clear_cache()
    body = api.get(f"/api/games/{HADES}/related")
    assert body.status_code == 200
    assert body.get_json() == {"genre": None, "items": []}
