"""Listas: criação, edição, visibilidade, jogos, ordem e permissões."""
from __future__ import annotations

import pytest

from . import fake_rawg
from .conftest import CELESTE, HADES, HOLLOW

OTHER = fake_rawg.by_name("Portal 2")["id"]


def make_list(client, title="Melhores indies", **extra):
    response = client.post("/api/lists", {"title": title, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["list"]


def add(client, list_id, rawg_id):
    return client.post(f"/api/lists/{list_id}/games", {"rawg_id": rawg_id})


def titles(body):
    return [item["game"]["name"] for item in body["list"]["items"]]


def test_create_list_defaults_to_public(ana):
    data = make_list(ana, description="Para jogar com calma.")
    assert data["title"] == "Melhores indies"
    assert data["description"] == "Para jogar com calma."
    assert data["is_public"] is True
    assert data["owner"]["username"] == "ana"
    assert data["game_count"] == 0 and data["items"] == [] and data["is_owner"] is True
    assert "created_at" in data


@pytest.mark.parametrize(
    "payload, field",
    [
        ({}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 81}, "title"),
        ({"title": "ok", "description": "x" * 501}, "description"),
        ({"title": "ok", "is_public": "sim"}, "is_public"),
    ],
)
def test_list_validation(ana, payload, field):
    response = ana.post("/api/lists", payload)
    assert response.status_code == 422
    assert field in response.get_json()["error"]["fields"]


def test_add_games_in_order_and_build_covers(ana):
    lst = make_list(ana)
    for rawg_id in (HADES, CELESTE, HOLLOW):
        assert add(ana, lst["id"], rawg_id).status_code == 201
    body = ana.get(f"/api/lists/{lst['id']}").get_json()
    assert titles(body) == ["Hades", "Celeste", "Hollow Knight"]
    assert [i["position"] for i in body["list"]["items"]] == [0, 1, 2]
    assert body["list"]["game_count"] == 3
    assert len(body["list"]["covers"]) == 3
    assert body["list"]["covers"][0]["name"] == "Hades"


def test_covers_are_limited_to_four(ana):
    lst = make_list(ana)
    for game in fake_rawg.GAMES[:6]:
        add(ana, lst["id"], game["id"])
    assert len(ana.get(f"/api/lists/{lst['id']}").get_json()["list"]["covers"]) == 4


def test_a_game_cannot_be_added_twice(ana):
    lst = make_list(ana)
    add(ana, lst["id"], HADES)
    again = add(ana, lst["id"], HADES)
    assert again.status_code == 409 and again.get_json()["error"]["code"] == "already_in_list"


@pytest.mark.parametrize("payload", [{}, {"rawg_id": "abc"}, {"rawg_id": -1}, {"rawg_id": True}, {"rawg_id": 1.5}])
def test_add_game_validates_input(ana, payload):
    lst = make_list(ana)
    assert ana.post(f"/api/lists/{lst['id']}/games", payload).status_code == 422


def test_add_unknown_game_is_404(ana):
    lst = make_list(ana)
    assert add(ana, lst["id"], 123456789).status_code == 404


def test_reorder_games(ana):
    lst = make_list(ana)
    for rawg_id in (HADES, CELESTE, HOLLOW):
        add(ana, lst["id"], rawg_id)
    response = ana.put(f"/api/lists/{lst['id']}/order", {"rawg_ids": [HOLLOW, HADES, CELESTE]})
    assert response.status_code == 200
    assert titles(response.get_json()) == ["Hollow Knight", "Hades", "Celeste"]
    assert titles(ana.get(f"/api/lists/{lst['id']}").get_json()) == ["Hollow Knight", "Hades", "Celeste"]


@pytest.mark.parametrize(
    "order",
    [
        [HADES, CELESTE],  # falta um
        [HADES, CELESTE, HOLLOW, OTHER],  # sobra um
        [HADES, HADES, CELESTE],  # repetido
        [HADES, CELESTE, 1],  # estranho
        "hades",
        [HADES, "x", CELESTE],
    ],
)
def test_reorder_rejects_inconsistent_orders(ana, order):
    lst = make_list(ana)
    for rawg_id in (HADES, CELESTE, HOLLOW):
        add(ana, lst["id"], rawg_id)
    assert ana.put(f"/api/lists/{lst['id']}/order", {"rawg_ids": order}).status_code == 422
    assert titles(ana.get(f"/api/lists/{lst['id']}").get_json()) == ["Hades", "Celeste", "Hollow Knight"]


def test_remove_game_keeps_positions_dense(ana):
    lst = make_list(ana)
    for rawg_id in (HADES, CELESTE, HOLLOW):
        add(ana, lst["id"], rawg_id)
    response = ana.delete(f"/api/lists/{lst['id']}/games/{CELESTE}")
    assert response.status_code == 200
    assert [i["position"] for i in response.get_json()["list"]["items"]] == [0, 1]
    assert titles(response.get_json()) == ["Hades", "Hollow Knight"]
    assert ana.delete(f"/api/lists/{lst['id']}/games/{CELESTE}").status_code == 404


def test_edit_and_delete_list(ana):
    lst = make_list(ana)
    updated = ana.patch(f"/api/lists/{lst['id']}", {"title": "Novo título", "description": None, "is_public": False})
    assert updated.status_code == 200
    data = updated.get_json()["list"]
    assert (data["title"], data["description"], data["is_public"]) == ("Novo título", None, False)
    assert ana.patch(f"/api/lists/{lst['id']}", {"title": ""}).status_code == 422
    assert ana.delete(f"/api/lists/{lst['id']}").status_code == 200
    assert ana.get(f"/api/lists/{lst['id']}").status_code == 404


def test_only_the_owner_can_change_a_public_list(ana, bruno):
    lst = make_list(ana)
    add(ana, lst["id"], HADES)
    assert bruno.patch(f"/api/lists/{lst['id']}", {"title": "roubada"}).status_code == 403
    assert add(bruno, lst["id"], CELESTE).status_code == 403
    assert bruno.delete(f"/api/lists/{lst['id']}/games/{HADES}").status_code == 403
    assert bruno.put(f"/api/lists/{lst['id']}/order", {"rawg_ids": [HADES]}).status_code == 403
    assert bruno.delete(f"/api/lists/{lst['id']}").status_code == 403
    body = bruno.get(f"/api/lists/{lst['id']}").get_json()["list"]
    assert body["title"] == "Melhores indies" and body["is_owner"] is False and body["game_count"] == 1


def test_private_lists_are_invisible_to_everyone_but_the_owner(ana, bruno, api):
    lst = make_list(ana, "Segredo", is_public=False)
    add(ana, lst["id"], HADES)
    for visitor in (bruno, api):
        assert visitor.get(f"/api/lists/{lst['id']}").status_code == 404
    assert bruno.patch(f"/api/lists/{lst['id']}", {"title": "x"}).status_code == 404  # nem confirma que existe
    assert ana.get(f"/api/lists/{lst['id']}").status_code == 200
    assert "Segredo" not in str(bruno.get("/api/lists").get_json())
    assert "Segredo" not in str(bruno.get("/api/users/ana/lists").get_json())
    assert "Segredo" in str(ana.get("/api/users/ana/lists").get_json())
    assert "Segredo" in str(ana.get("/api/me/lists").get_json())
    assert bruno.get("/api/search?q=Segredo").get_json()["lists"] == []


def test_making_a_list_private_hides_it_again(ana, bruno):
    lst = make_list(ana)
    add(ana, lst["id"], HADES)
    assert bruno.get(f"/api/lists/{lst['id']}").status_code == 200
    ana.patch(f"/api/lists/{lst['id']}", {"is_public": False})
    assert bruno.get(f"/api/lists/{lst['id']}").status_code == 404


def test_community_listing_shows_only_public_lists_with_games(ana, bruno):
    empty = make_list(ana, "Vazia")
    full = make_list(ana, "Com jogos")
    add(ana, full["id"], HADES)
    hidden = make_list(ana, "Oculta", is_public=False)
    add(ana, hidden["id"], HADES)
    names = [item["title"] for item in bruno.get("/api/lists").get_json()["items"]]
    assert names == ["Com jogos"]
    assert empty["id"] != full["id"]


def test_community_listing_pagination_and_search(ana):
    for index in range(5):
        lst = make_list(ana, f"Lista {index}")
        add(ana, lst["id"], HADES)
    page = ana.get("/api/lists?per_page=2").get_json()
    assert len(page["items"]) == 2 and page["has_next"] is True
    found = ana.get("/api/lists?q=Lista 3").get_json()["items"]
    assert [i["title"] for i in found] == ["Lista 3"]
    assert ana.get("/api/lists?q=%25").get_json()["items"] == []  # '%' não vira curinga


def test_list_deletion_cascades_to_its_games_and_activity(ana, app):
    lst = make_list(ana)
    add(ana, lst["id"], HADES)
    ana.delete(f"/api/lists/{lst['id']}")
    import sqlite3

    conn = sqlite3.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM list_games").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM activities WHERE type = 'list_created'").fetchone()[0] == 0


def test_the_games_in_a_list_are_independent_of_the_library(ana):
    lst = make_list(ana)
    add(ana, lst["id"], HADES)
    assert ana.get("/api/library").get_json()["counts"]["total"] == 0


def test_game_page_tells_which_lists_contain_the_game(ana):
    first, second = make_list(ana, "A"), make_list(ana, "B")
    add(ana, first["id"], HADES)
    viewer = ana.get(f"/api/games/{HADES}").get_json()["viewer"]
    assert viewer["list_ids"] == [first["id"]]
    assert second["id"] not in viewer["list_ids"]


def test_list_limit_per_user(ana, monkeypatch):
    from app.services import lists as lists_service

    monkeypatch.setattr(lists_service, "MAX_LISTS_PER_USER", 2)
    make_list(ana, "1")
    make_list(ana, "2")
    third = ana.post("/api/lists", {"title": "3"})
    assert third.status_code == 409 and third.get_json()["error"]["code"] == "limit_reached"
