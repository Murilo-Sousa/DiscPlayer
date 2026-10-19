"""Cadastro, login, logout, sessão, CSRF e perfil da conta."""
from __future__ import annotations

import sqlite3

import pytest

from app import create_app

from .conftest import PASSWORD, Api


def test_register_creates_account_and_logs_in(api, app):
    response = api.register("ana", display_name="Ana Souza")
    body = response.get_json()
    assert body["user"]["username"] == "ana"
    assert body["user"]["display_name"] == "Ana Souza"
    assert "password" not in body["user"] and "password_hash" not in body["user"]

    me = api.get("/api/auth/me").get_json()
    assert me["user"]["username"] == "ana"


def test_register_defaults_display_name_and_normalizes_username(api):
    api.register("ANA_99", email="ANA@Exemplo.COM")
    user = api.get("/api/auth/me").get_json()["user"]
    assert user["username"] == "ana_99"
    assert user["display_name"] == "ana_99"
    assert user["email"] == "ana@exemplo.com"


def test_password_is_stored_as_salted_hash_never_plaintext(api, app):
    api.register("ana")
    stored = sqlite3.connect(app.config["DATABASE"]).execute(
        "SELECT password_hash FROM users WHERE username = 'ana'"
    ).fetchone()[0]
    assert stored != PASSWORD and PASSWORD not in stored
    assert stored.startswith("scrypt:")
    # dois cadastros com a mesma senha geram hashes diferentes (sal)
    api2 = Api(app)
    api2.register("bia", password=PASSWORD)
    other = sqlite3.connect(app.config["DATABASE"]).execute(
        "SELECT password_hash FROM users WHERE username = 'bia'"
    ).fetchone()[0]
    assert other != stored


def test_session_cookie_is_httponly_and_samesite_lax(api):
    response = api.register("ana")
    cookie = next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("discplayer_session="))
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie  # fora de produção o cookie também funciona em http://localhost


def test_production_requires_secret_key_and_marks_cookie_secure(tmp_path):
    base = {"TESTING": True, "DATABASE": str(tmp_path / "p.db"), "IS_PRODUCTION": True, "RATELIMIT_ENABLED": False}
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({**base, "SECRET_KEY": None})
    app = create_app({**base, "SECRET_KEY": "x" * 40, "SESSION_COOKIE_SECURE": True})
    client = Api(app)
    response = client.client.get("/api/auth/me")
    cookie = next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("discplayer_session="))
    assert "Secure" in cookie and "HttpOnly" in cookie


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"username": "ab", "email": "a@b.co", "password": PASSWORD}, "username"),
        ({"username": "Ana Souza", "email": "a@b.co", "password": PASSWORD}, "username"),
        ({"username": "admin", "email": "a@b.co", "password": PASSWORD}, "username"),
        ({"username": "ana", "email": "sem-arroba", "password": PASSWORD}, "email"),
        ({"username": "ana", "email": "a@b.co", "password": "curta"}, "password"),
        ({"username": "ana", "email": "a@b.co", "password": "password1"}, "password"),
        ({"username": "ana", "email": "a@b.co", "password": "x" * 129}, "password"),
        ({"username": "ana", "email": "a@b.co"}, "password"),
        ({"email": "a@b.co", "password": PASSWORD}, "username"),
    ],
)
def test_register_rejects_invalid_fields(api, payload, field):
    response = api.post("/api/auth/register", payload)
    assert response.status_code == 422
    assert field in response.get_json()["error"]["fields"]


def test_register_rejects_password_equal_to_username(api):
    response = api.post("/api/auth/register", {"username": "ana_senha", "email": "a@b.co", "password": "ana_senha"})
    assert response.status_code == 422
    assert "password" in response.get_json()["error"]["fields"]


def test_register_requires_json_object(api):
    response = api.client.post(
        "/api/auth/register", data="não é json", headers={"X-CSRF-Token": api._token(), "Content-Type": "text/plain"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"


def test_username_and_email_are_unique_ignoring_case(api, app):
    api.register("ana", email="ana@exemplo.com")
    other = Api(app)
    dup_user = other.post("/api/auth/register", {"username": "ANA", "email": "outra@exemplo.com", "password": PASSWORD})
    assert dup_user.status_code == 409
    assert "username" in dup_user.get_json()["error"]["fields"]
    dup_mail = other.post("/api/auth/register", {"username": "bia", "email": "ANA@exemplo.com", "password": PASSWORD})
    assert dup_mail.status_code == 409
    assert "email" in dup_mail.get_json()["error"]["fields"]


def test_login_by_username_or_email(app, api):
    api.register("ana", email="ana@exemplo.com")
    for identifier in ("ana", "ANA", "ana@exemplo.com", "  Ana@Exemplo.com "):
        fresh = Api(app)
        response = fresh.login(identifier)
        assert response.status_code == 200, identifier
        assert fresh.get("/api/auth/me").get_json()["user"]["username"] == "ana"


def test_wrong_password_and_unknown_user_get_the_same_error(app, api):
    api.register("ana")
    wrong = Api(app).login("ana", "senha-errada-123")
    unknown = Api(app).login("fantasma", "senha-errada-123")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()["error"] == unknown.get_json()["error"]
    assert wrong.get_json()["error"]["code"] == "invalid_credentials"


def test_login_requires_both_fields(api):
    response = api.post("/api/auth/login", {"identifier": "", "password": ""})
    assert response.status_code == 422
    assert set(response.get_json()["error"]["fields"]) == {"identifier", "password"}


def test_logout_ends_the_session(ana):
    assert ana.get("/api/auth/me").get_json()["user"] is not None
    response = ana.post("/api/auth/logout")
    assert response.status_code == 200
    ana.csrf = response.get_json()["csrf_token"]
    assert ana.get("/api/auth/me").get_json()["user"] is None
    assert ana.get("/api/library").status_code == 401


def test_login_rotates_the_session(app, api):
    api.register("ana")
    other = Api(app)
    before = other._token()
    other.login("ana")
    assert other.csrf != before  # sessão nova, token novo (contra session fixation)


def test_session_survives_server_restart(tmp_path):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "restart.db"),
        "SECRET_KEY": "chave-fixa-para-este-teste-0123456789",
        "RATELIMIT_ENABLED": False,
    }
    first = Api(create_app(config))
    first.register("ana")
    cookie = first.client.get_cookie("discplayer_session").value

    second = Api(create_app(config))  # "reinício": novo processo, mesmo banco e mesma chave
    second.client.set_cookie("discplayer_session", cookie, domain="localhost")
    assert second.get("/api/auth/me").get_json()["user"]["username"] == "ana"


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/api/library"),
        ("get", "/api/feed"),
        ("get", "/api/me/lists"),
        ("put", "/api/library/900001"),
        ("post", "/api/lists"),
        ("post", "/api/games/900001/reviews"),
        ("patch", "/api/auth/me"),
        ("put", "/api/users/ana/follow"),
        ("put", "/api/reviews/1/like"),
    ],
)
def test_protected_routes_require_login(api, method, url):
    response = getattr(api, method)(url, json={}) if method != "get" else api.get(url)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "auth_required"


def test_state_changing_requests_need_a_valid_csrf_token(ana):
    no_token = ana.post("/api/auth/logout", csrf=False)
    assert no_token.status_code == 403 and no_token.get_json()["error"]["code"] == "csrf_invalid"
    wrong = ana.post("/api/lists", {"title": "x"}, headers={"X-CSRF-Token": "falso"})
    assert wrong.status_code == 403
    assert ana.get("/api/auth/me").get_json()["user"] is not None  # a sessão não foi afetada


def test_cross_origin_writes_are_rejected_even_with_a_token(ana):
    response = ana.post("/api/lists", {"title": "Lista"}, headers={"Origin": "https://site-malicioso.example"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "origin_forbidden"


def test_allowed_dev_origin_is_accepted(ana):
    response = ana.post("/api/lists", {"title": "Lista"}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 201


def test_update_profile(ana):
    response = ana.patch(
        "/api/auth/me",
        {"display_name": "Ana S.", "bio": "Jogo de tudo.\nPrincipalmente RPG.", "avatar_url": "https://exemplo.com/a.png"},
    )
    assert response.status_code == 200
    user = response.get_json()["user"]
    assert user["display_name"] == "Ana S."
    assert user["bio"].startswith("Jogo de tudo.")
    assert user["avatar_url"] == "https://exemplo.com/a.png"
    assert ana.get("/api/auth/me").get_json()["user"]["bio"] == user["bio"]


def test_profile_clears_fields_with_null_and_rejects_bad_values(ana):
    ana.patch("/api/auth/me", {"bio": "oi"})
    cleared = ana.patch("/api/auth/me", {"bio": None}).get_json()["user"]
    assert cleared["bio"] is None

    for payload, field in [
        ({"avatar_url": "javascript:alert(1)"}, "avatar_url"),
        ({"avatar_url": "data:text/html,<script>1</script>"}, "avatar_url"),
        ({"avatar_url": "ftp://exemplo.com/a.png"}, "avatar_url"),
        ({"avatar_url": "http://exemplo.com/a.png"}, "avatar_url"),  # só https: a CSP bloqueia imagens http
        ({"bio": "x" * 281}, "bio"),
        ({"display_name": ""}, "display_name"),
        ({"display_name": "x" * 51}, "display_name"),
    ]:
        response = ana.patch("/api/auth/me", payload)
        assert response.status_code == 422, payload
        assert field in response.get_json()["error"]["fields"]


def test_profile_update_cannot_change_username_email_or_id(ana):
    ana.patch("/api/auth/me", {"username": "outro", "email": "novo@x.co", "id": 99, "password_hash": "x"})
    user = ana.get("/api/auth/me").get_json()["user"]
    assert (user["username"], user["email"], user["id"]) == ("ana", "ana@exemplo.com", ana.user["id"])


def test_login_is_rate_limited(app):
    limited = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"] + ".rl", "RATELIMIT_ENABLED": True})
    client = Api(limited)
    statuses = [client.login("ninguem", "senha-qualquer-1").status_code for _ in range(12)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    retry = client.login("ninguem", "senha-qualquer-1")
    assert retry.status_code == 429 and int(retry.headers["Retry-After"]) > 0
