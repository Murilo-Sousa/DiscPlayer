"""Exclusão da conta: confirmação por senha, remoção completa e sessões antigas."""
from __future__ import annotations

import sqlite3

import pytest

from app import create_app
from app import db as database

from . import images
from .conftest import CELESTE, HADES, PASSWORD, Api

URL = "/api/auth/me"


def delete_account(client, password=PASSWORD):
    return client.delete(URL, {"password": password})


def raw(app):
    connection = database.connect(app.config["DATABASE"])
    return connection


def rows_of(app, user_id):
    """Quantas linhas de cada tabela ainda apontam para esse usuário."""
    connection = raw(app)
    try:
        counts = {}
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            columns = [c["name"] for c in connection.execute(f"PRAGMA table_info({table})")]
            owners = [c for c in columns if c in ("user_id", "follower_id", "followed_id")]
            if table == "users":
                owners = ["id"]
            for column in owners:
                n = connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (user_id,)).fetchone()[0]
                counts[f"{table}.{column}"] = n
        return counts
    finally:
        connection.close()


def fill_account(ana, bruno):
    """Dados de todos os tipos para a ana, misturados com os do bruno."""
    ana.put(f"/api/library/{HADES}", {"status": "zerado", "started_at": "2025-01-01", "completed_at": "2025-01-20"})
    ana.post(f"/api/library/{HADES}/replay", {})
    ana.put(f"/api/library/{CELESTE}", {"status": "jogando", "is_favorite": True})
    bruno.put(f"/api/library/{HADES}", {"status": "zerado"})
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 10, "body": "Obra-prima.", "has_spoilers": True})
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 6, "body": "Ok."})
    ana.play(CELESTE)
    ana.post(f"/api/games/{CELESTE}/reviews", {"rating": 8})
    ana_review = ana.get("/api/users/ana/reviews").get_json()["items"]
    bruno_review = bruno.get("/api/users/bruno/reviews").get_json()["items"][0]
    for item in ana_review:
        bruno.put(f"/api/reviews/{item['id']}/like")  # bruno curte as reviews da ana
    ana.put(f"/api/reviews/{bruno_review['id']}/like")  # ana curte a review do bruno
    ana.put("/api/users/bruno/follow")
    bruno.put("/api/users/ana/follow")
    for owner, title in ((ana, "Lista da ana"), (bruno, "Lista do bruno")):
        list_id = owner.post("/api/lists", {"title": title}).get_json()["list"]["id"]
        owner.post(f"/api/lists/{list_id}/games", {"rawg_id": HADES})
    ana.upload("/api/auth/me/avatar", images.encode(images.two_halves(300, 300), "PNG"))
    return bruno_review["id"]


# ----------------------------------------------------------------- confirmação
def test_wrong_password_deletes_nothing(ana):
    response = delete_account(ana, "senha-errada-123")
    assert response.status_code == 403
    error = response.get_json()["error"]
    assert error["code"] == "invalid_password" and "password" in error["fields"]
    assert ana.get("/api/auth/me").get_json()["user"]["username"] == "ana"


@pytest.mark.parametrize("body", [{}, {"password": ""}, {"password": None}, {"password": 123}, {"password": ["x"]}])
def test_missing_or_malformed_password_is_a_422(ana, body):
    response = ana.delete(URL, body)
    assert response.status_code == 422 and "password" in response.get_json()["error"]["fields"]
    assert ana.get("/api/auth/me").get_json()["user"] is not None


def test_a_non_json_body_is_refused(ana):
    response = ana.client.delete(URL, headers={"X-CSRF-Token": ana._token()})
    assert response.status_code == 400
    assert ana.get("/api/auth/me").get_json()["user"] is not None


def test_needs_login_and_csrf_and_a_trusted_origin(api, ana):
    assert delete_account(api).status_code == 401
    assert ana.delete(URL, {"password": PASSWORD}, csrf=False).status_code == 403
    response = ana.delete(URL, {"password": PASSWORD}, headers={"Origin": "https://site-malicioso.example"})
    assert response.status_code == 403
    assert ana.get("/api/auth/me").get_json()["user"] is not None


def test_someone_elses_password_does_not_work(ana, bruno):
    other = "outra-senha-longa-456"
    carla = Api(ana.client.application)
    carla.register("carla", password=other)
    assert carla.delete(URL, {"password": PASSWORD}).status_code == 403  # a senha da ana não serve para a carla
    assert carla.get("/api/auth/me").get_json()["user"] is not None


def test_password_attempts_are_rate_limited(app):
    limited = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"] + ".rl", "RATELIMIT_ENABLED": True})
    client = Api(limited)
    client.register("ana")
    statuses = [delete_account(client, "errada-1234567").status_code for _ in range(7)]
    assert statuses[:5] == [403] * 5 and statuses[5] == 429
    assert delete_account(client).status_code == 429  # nem a senha certa passa enquanto o limite vale
    assert client.get("/api/auth/me").get_json()["user"] is not None


# ---------------------------------------------------------------- o que acontece
def test_deleting_ends_the_session_and_frees_the_username_and_email(ana, api):
    response = delete_account(ana)
    assert response.status_code == 200 and response.get_json()["user"] is None
    assert ana.get("/api/auth/me").get_json()["user"] is None
    assert api.login("ana").status_code == 401 and api.login("ana@exemplo.com").status_code == 401
    assert api.get("/api/users/ana").status_code == 404
    assert api.get("/api/search?q=ana").get_json()["users"] == []
    again = Api(ana.client.application)
    again.register("ana")  # nome e e-mail ficam livres para um cadastro novo
    assert again.get("/api/users/ana").get_json()["stats"]["games"] == 0  # e a conta nova nasce vazia


def test_every_trace_of_the_account_is_removed_and_nobody_elses_is_touched(ana, bruno, app):
    bruno_review_id = fill_account(ana, bruno)
    ana_id, bruno_id = ana.user["id"], bruno.user["id"]
    before = rows_of(app, ana_id)
    assert sum(before.values()) > 12, before  # a conta tinha dados de todos os tipos
    bruno_before = rows_of(app, bruno_id)
    connection = raw(app)
    games_before = connection.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    connection.close()

    assert delete_account(ana).status_code == 200

    assert all(n == 0 for n in rows_of(app, ana_id).values()), rows_of(app, ana_id)
    connection = raw(app)
    try:
        assert connection.execute("SELECT COUNT(*) FROM user_avatars WHERE user_id = ?", (ana_id,)).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == games_before  # catálogo compartilhado
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []  # nada ficou órfão
    finally:
        connection.close()

    # o que é do bruno continua inteiro (a curtida da ana na review dele foi embora junto com ela)
    after = rows_of(app, bruno_id)
    assert after["library_entries.user_id"] == bruno_before["library_entries.user_id"]
    assert after["reviews.user_id"] == bruno_before["reviews.user_id"] == 1
    assert after["lists.user_id"] == bruno_before["lists.user_id"] == 1
    assert after["follows.follower_id"] == 0 and after["follows.followed_id"] == 0  # só ligavam à ana
    review = bruno.get(f"/api/reviews/{bruno_review_id}").get_json()["review"]
    assert review["like_count"] == 0 and review["body"] == "Ok."
    assert bruno.get("/api/users/bruno").get_json()["stats"]["followers"] == 0
    assert bruno.get("/api/users/bruno").get_json()["stats"]["lists"] == 1


def test_the_game_pages_recompute_without_the_deleted_accounts_review(ana, bruno):
    fill_account(ana, bruno)
    before = bruno.get(f"/api/games/{HADES}").get_json()["community"]
    assert before["count"] == 2 and before["average"] == 8
    delete_account(ana)
    after = bruno.get(f"/api/games/{HADES}").get_json()
    assert after["community"]["count"] == 1 and after["community"]["average"] == 6
    assert after["community"]["library"]["total"] == 1
    assert [r["user"]["username"] for r in after["reviews"]] == ["bruno"]
    assert all(a["user"]["username"] != "ana" for a in bruno.get("/api/activity").get_json()["items"])
    assert bruno.get("/api/feed").get_json()["items"] == []


def test_the_photo_of_a_deleted_account_stops_being_served(ana, api):
    ana.upload("/api/auth/me/avatar", images.encode(images.two_halves(300, 300), "PNG"))
    url = ana.get("/api/auth/me").get_json()["user"]["avatar_url"]
    assert api.get(url).status_code == 200
    delete_account(ana)
    assert api.get(url).status_code == 404


def test_the_accounts_lists_are_gone(ana, api):
    list_id = ana.post("/api/lists", {"title": "Minha lista"}).get_json()["list"]["id"]
    ana.post(f"/api/lists/{list_id}/games", {"rawg_id": HADES})
    delete_account(ana)
    assert api.get(f"/api/lists/{list_id}").status_code == 404
    assert api.get("/api/lists").get_json()["items"] == []


# ------------------------------------------------------- cookies de contas excluídas
def copy_cookie(source: Api, target: Api) -> None:
    cookie = source.client.get_cookie("discplayer_session")
    target.client.set_cookie("discplayer_session", cookie.value)
    target.csrf = source.csrf


def test_another_device_loses_access_when_the_account_is_deleted(ana, app):
    other_device = Api(app)
    copy_cookie(ana, other_device)
    assert other_device.get("/api/auth/me").get_json()["user"]["username"] == "ana"
    delete_account(ana)
    assert other_device.get("/api/auth/me").get_json()["user"] is None
    assert other_device.patch(URL, {"bio": "ainda aqui?"}).status_code == 401


def test_a_deleted_accounts_cookie_never_works_for_the_next_account_that_reuses_its_id(ana, bruno, app):
    # O SQLite reaproveita o maior id depois de uma exclusão: a próxima conta herda o id do bruno.
    old_cookie_holder = Api(app)
    copy_cookie(bruno, old_cookie_holder)
    old_id = bruno.user["id"]
    delete_account(bruno)

    carla = Api(app)
    carla.register("carla")
    assert carla.user["id"] == old_id  # a condição perigosa realmente aconteceu
    assert carla.get("/api/auth/me").get_json()["user"]["username"] == "carla"

    assert old_cookie_holder.get("/api/auth/me").get_json()["user"] is None
    assert old_cookie_holder.patch(URL, {"bio": "sou o bruno"}).status_code == 401
    assert carla.get("/api/auth/me").get_json()["user"]["bio"] is None  # nada vazou para a carla


def test_a_forged_or_missing_session_key_is_not_accepted(ana, app):
    connection = raw(app)
    connection.execute("UPDATE users SET session_key = 'outra-chave' WHERE id = ?", (ana.user["id"],))
    connection.close()
    assert ana.get("/api/auth/me").get_json()["user"] is None  # o cookie guarda a chave antiga


@pytest.mark.parametrize("empty", ["NULL", "''"])
def test_login_creates_a_missing_session_key_instead_of_logging_straight_out(ana, app, empty):
    connection = raw(app)
    connection.execute(f"UPDATE users SET session_key = {empty} WHERE id = ?", (ana.user["id"],))
    connection.close()
    phone = Api(app)
    assert phone.login("ana").status_code == 200
    assert phone.get("/api/auth/me").get_json()["user"]["username"] == "ana"
    connection = raw(app)
    try:
        stored = connection.execute("SELECT session_key FROM users WHERE id = ?", (ana.user["id"],)).fetchone()[0]
    finally:
        connection.close()
    assert stored and len(stored) == 32


def test_logging_in_again_still_works_on_several_devices(ana, app):
    phone = Api(app)
    assert phone.login("ana").status_code == 200
    assert phone.get("/api/auth/me").get_json()["user"]["username"] == "ana"
    assert ana.get("/api/auth/me").get_json()["user"]["username"] == "ana"
    ana.post("/api/auth/logout")
    assert ana.get("/api/auth/me").get_json()["user"] is None
    assert phone.get("/api/auth/me").get_json()["user"]["username"] == "ana"  # sair não derruba o outro aparelho


def test_the_session_key_is_never_sent_to_the_browser(ana):
    me = ana.get("/api/auth/me").get_json()
    assert "session_key" not in str(me) and "password_hash" not in str(me)
