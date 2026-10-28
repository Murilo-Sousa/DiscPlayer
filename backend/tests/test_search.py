"""Pesquisa global: jogos (RAWG), jogadores, listas e reviews."""
from __future__ import annotations

import pytest

from app.services import rawg

from .conftest import CELESTE, HADES


def test_search_returns_every_category(ana, bruno):
    bruno.put(f"/api/library/{HADES}", {"status": "zerado"})
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Hades é viciante."})
    lst = bruno.post("/api/lists", {"title": "Favoritos do Hades"}).get_json()["list"]
    bruno.post(f"/api/lists/{lst['id']}/games", {"rawg_id": HADES})
    body = ana.get("/api/search?q=hades").get_json()
    assert body["query"] == "hades"
    assert {g["name"] for g in body["games"]["items"]} == {"Hades", "Hades II"}
    assert body["games"]["error"] is None
    assert [r["excerpt"] for r in body["reviews"]] == ["Hades é viciante."]
    assert "body" not in body["reviews"][0]
    assert [l["title"] for l in body["lists"]] == ["Favoritos do Hades"]


def test_search_finds_users_by_username_or_display_name(ana, make_user):
    make_user("maria_silva", display_name="Maria da Silva")
    by_username = ana.get("/api/search?q=maria_s").get_json()["users"]
    by_display = ana.get("/api/search?q=da silva").get_json()["users"]
    assert [u["username"] for u in by_username] == ["maria_silva"]
    assert [u["username"] for u in by_display] == ["maria_silva"]
    assert set(by_username[0]) == {"username", "display_name", "avatar_url", "bio"}
    assert ana.get("/api/search?q=inexistente").get_json()["users"] == []


def test_search_handles_empty_results(ana):
    body = ana.get("/api/search?q=zzzzzzzz").get_json()
    assert body["games"]["items"] == [] and body["users"] == [] and body["lists"] == [] and body["reviews"] == []


@pytest.mark.parametrize("term", ["", " ", "a", "x" * 101])
def test_search_validates_length(ana, term):
    response = ana.get(f"/api/search?q={term}")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_search_does_not_treat_like_wildcards_as_wildcards(ana, make_user):
    make_user("bruno")
    body = ana.get("/api/search?q=%25%25").get_json()  # "%%"
    assert body["users"] == [] and body["lists"] == [] and body["reviews"] == []
    assert ana.get("/api/search?q=_r_n").get_json()["users"] == []


def test_search_survives_sql_injection_attempts(ana):
    response = ana.get("/api/search?q=' OR 1=1 --")
    assert response.status_code == 200
    assert response.get_json()["users"] == []
    assert ana.get("/api/users/ana';DROP TABLE users;--").status_code == 404
    assert ana.get("/api/auth/me").get_json()["user"]["username"] == "ana"


def test_search_degrades_gracefully_when_rawg_is_down(ana, bruno, monkeypatch):
    bruno.put(f"/api/library/{HADES}", {"status": "zerado"})
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Hades é viciante."})

    def down(*_a, **_k):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    rawg.clear_cache()
    response = ana.get("/api/search?q=hades")
    assert response.status_code == 200
    body = response.get_json()
    assert body["games"]["items"] == []
    assert body["games"]["error"]["code"] == "rawg_unavailable"
    assert len(body["reviews"]) == 1  # os resultados locais continuam chegando


def test_search_works_for_visitors(api):
    assert api.get("/api/search?q=celeste").get_json()["games"]["items"][0]["rawg_id"] == CELESTE
