"""Fixtures compartilhadas. Nenhum teste fala com a RAWG de verdade."""
from __future__ import annotations

import io

import pytest

from app import create_app
from app.security import reset_rate_limits
from app.services import rawg

from . import fake_rawg

PASSWORD = "uma-senha-longa-123"


class Api:
    """Cliente de testes que cuida do token de CSRF como o front-end faz."""

    def __init__(self, app):
        self.client = app.test_client()
        self.csrf: str | None = None
        self.user: dict | None = None
        self.headers: dict[str, str] = {}

    def _token(self) -> str:
        if self.csrf is None:
            self.csrf = self.client.get("/api/auth/me").get_json()["csrf_token"]
        return self.csrf

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def _send(self, method, url, json=None, csrf=True, headers=None):
        merged = dict(self.headers)
        if csrf:
            merged["X-CSRF-Token"] = self._token()
        merged.update(headers or {})  # cabeçalhos explícitos vencem (permite testar token falso)
        return getattr(self.client, method)(url, json=json, headers=merged)

    def post(self, url, json=None, **kw):
        return self._send("post", url, json, **kw)

    def put(self, url, json=None, **kw):
        return self._send("put", url, json, **kw)

    def patch(self, url, json=None, **kw):
        return self._send("patch", url, json, **kw)

    def delete(self, url, json=None, **kw):
        return self._send("delete", url, json, **kw)

    def upload(self, url, file=None, *, name="file", filename="foto.png", csrf=True, headers=None, method="post"):
        """Envia um arquivo como multipart/form-data (como o <input type=file> do navegador)."""
        merged = dict(self.headers)
        if csrf:
            merged["X-CSRF-Token"] = self._token()
        merged.update(headers or {})
        data = {} if file is None else {name: (io.BytesIO(file), filename)}
        return getattr(self.client, method)(url, data=data, headers=merged, content_type="multipart/form-data")

    def register(self, username="ana", email=None, password=PASSWORD, **extra):
        body = {"username": username, "email": email or f"{username}@exemplo.com", "password": password, **extra}
        response = self.post("/api/auth/register", body)
        assert response.status_code == 201, response.get_json()
        self.csrf = response.get_json()["csrf_token"]
        self.user = response.get_json()["user"]
        return response

    def login(self, identifier, password=PASSWORD):
        response = self.post("/api/auth/login", {"identifier": identifier, "password": password})
        if response.status_code == 200:
            self.csrf = response.get_json()["csrf_token"]
            self.user = response.get_json()["user"]
        return response


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    rawg.clear_cache()
    reset_rate_limits()
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "RATELIMIT_ENABLED": False,
            "RAWG_API_KEY": "chave-de-teste",
            "FRONTEND_DIST": str(tmp_path / "dist-inexistente"),
        }
    )
    yield application
    rawg.clear_cache()


@pytest.fixture
def api(app) -> Api:
    return Api(app)


@pytest.fixture
def make_user(app):
    """Cria um usuário já autenticado em um cliente próprio."""

    def factory(username: str, **extra) -> Api:
        client = Api(app)
        client.register(username, **extra)
        return client

    return factory


@pytest.fixture
def ana(make_user) -> Api:
    return make_user("ana")


@pytest.fixture
def bruno(make_user) -> Api:
    return make_user("bruno")


# ids sintéticos da RAWG simulada
HADES = fake_rawg.by_name("Hades")["id"]
CELESTE = fake_rawg.by_name("Celeste")["id"]
HOLLOW = fake_rawg.by_name("Hollow Knight")["id"]
ZELDA = fake_rawg.by_name("The Legend of Zelda: Breath of the Wild")["id"]
