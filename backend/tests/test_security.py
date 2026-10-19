"""Cabeçalhos, CORS, limites de entrada, erros seguros e entrega do front-end."""
from __future__ import annotations

import pytest

from app import create_app

from .conftest import PASSWORD, Api


def test_security_headers_on_every_response(api):
    response = api.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cache-Control"] == "no-store"  # respostas da API nunca ficam em cache


def test_cors_allows_only_configured_origins_with_credentials(api):
    allowed = api.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert allowed.headers["Access-Control-Allow-Credentials"] == "true"
    denied = api.get("/api/health", headers={"Origin": "https://site-malicioso.example"})
    assert "Access-Control-Allow-Origin" not in denied.headers
    assert "Access-Control-Allow-Credentials" not in denied.headers
    assert denied.headers["Vary"].find("Origin") >= 0


def test_cors_preflight(api):
    ok = api.client.options(
        "/api/lists",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert ok.status_code == 204
    assert "X-CSRF-Token" in ok.headers["Access-Control-Allow-Headers"]
    assert "POST" in ok.headers["Access-Control-Allow-Methods"]
    bad = api.client.options("/api/lists", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in bad.headers


def test_oversized_bodies_are_rejected(ana):
    response = ana.post("/api/lists", {"title": "ok", "description": "x" * 100_000})
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "payload_too_large"


def test_internal_errors_do_not_leak_details(app, api, monkeypatch):
    from app.routes import health

    def boom():
        raise RuntimeError("segredo: senha=abc123 em /home/usuario/app.py")

    monkeypatch.setitem(app.view_functions, "health.health", boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.testing = False
    response = api.get("/api/health")
    assert response.status_code == 500
    text = response.get_data(as_text=True)
    assert "abc123" not in text and "Traceback" not in text and "/home/" not in text
    assert response.get_json()["error"]["code"] == "internal_error"
    app.testing = True
    assert health  # (import usado apenas para deixar claro qual rota foi substituída)


@pytest.mark.parametrize("method, url", [("post", "/api/health"), ("delete", "/api/games"), ("put", "/api/search")])
def test_wrong_methods_return_a_clean_json_error(api, method, url):
    response = getattr(api, method)(url, json={})
    assert response.status_code in (404, 405)
    assert "error" in response.get_json()


def test_unknown_api_routes_are_json_404s_not_html(api):
    response = api.get("/api/nao-existe")
    assert response.status_code == 404
    assert response.is_json and response.get_json()["error"]["code"] == "not_found"


def test_stored_text_is_never_interpreted_as_markup_by_the_api(ana):
    """O JSON devolve o texto cru; quem escapa é o React (veja os testes do front-end)."""
    payload = '<img src=x onerror="alert(1)">'
    ana.patch("/api/auth/me", {"bio": payload, "display_name": "<b>Ana</b>"})
    user = ana.get("/api/auth/me").get_json()["user"]
    assert user["bio"] == payload and user["display_name"] == "<b>Ana</b>"
    assert ana.get("/api/auth/me").mimetype == "application/json"


def test_login_hides_whether_an_account_exists(app, api):
    api.register("ana")
    existing = Api(app).post("/api/auth/login", {"identifier": "ana", "password": "errada-errada-1"})
    missing = Api(app).post("/api/auth/login", {"identifier": "ninguem", "password": "errada-errada-1"})
    assert existing.get_json() == missing.get_json()


def test_rate_limit_applies_per_endpoint_group(tmp_path):
    limited = create_app({"TESTING": True, "DATABASE": str(tmp_path / "r.db"), "RATELIMIT_ENABLED": True})
    client = Api(limited)
    client.register("ana")
    results = [client.get("/api/search?q=zelda").status_code for _ in range(95)]
    assert results[:90] == [200] * 90 and 429 in results[90:]
    assert client.get("/api/library").status_code == 200  # outros endpoints seguem liberados


# ------------------------------------------------------------- front-end compilado
@pytest.fixture
def spa(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>DiscPlayer</title><div id=root></div>")
    (dist / "assets" / "app-abc123.js").write_text("console.log('ok')")
    (tmp_path / "segredo.txt").write_text("fora do dist")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "s.db"), "FRONTEND_DIST": str(dist)})
    return Api(app)


def test_spa_serves_index_for_client_side_routes_with_csp(spa):
    for path in ("/", "/jogos", "/u/ana", "/listas/12"):
        response = spa.get(path)
        assert response.status_code == 200 and b"DiscPlayer" in response.data
        csp = response.headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        assert response.headers["Cache-Control"] == "no-cache"


def test_spa_serves_hashed_assets_with_long_cache(spa):
    response = spa.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["Cache-Control"]


@pytest.mark.parametrize("path", ["/../segredo.txt", "/assets/../../segredo.txt", "/%2e%2e/segredo.txt", "/..%2fsegredo.txt"])
def test_spa_blocks_path_traversal(spa, path):
    response = spa.get(path)
    assert b"fora do dist" not in response.data


def test_spa_never_answers_api_paths_with_html(spa):
    response = spa.get("/api/inexistente")
    assert response.status_code == 404 and response.is_json


def test_missing_build_explains_what_to_do(api):
    response = api.get("/")
    assert response.status_code == 404
    assert "npm run" in response.get_data(as_text=True)
