"""Infraestrutura do teste de ponta a ponta.

Cada teste recebe uma "pilha" própria e descartável:
  * um banco SQLite novo e vazio;
  * a API Flask de verdade, servindo o front-end compilado (frontend/dist);
  * uma RAWG de mentira (tests/fake_rawg_server.py), para não depender de chave nem de internet.

As imagens de capa (media.rawg.io) são interceptadas no navegador e trocadas por desenhos
gerados na hora, então nada sai da máquina.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.services import rawg as rawg_service  # noqa: E402
from tests.fake_rawg_server import create_fake_server  # noqa: E402

DIST = Path(os.environ.get("E2E_DIST", ROOT / "frontend" / "dist"))


def pytest_collection_modifyitems(config, items):
    if not (DIST / "index.html").is_file():
        skip = pytest.mark.skip(
            reason=f"Front-end não compilado em {DIST}. Rode `npm run build` em frontend/ (ou defina E2E_DIST)."
        )
        for item in items:
            item.add_marker(skip)


class _Server:
    """Servidor WSGI em uma thread, que pode ser parado e religado na mesma porta."""

    def __init__(self, app, port: int = 0):
        self.app = app
        self.port = port
        self._httpd = None
        self._thread = None

    def start(self) -> "_Server":
        self._httpd = make_server("127.0.0.1", self.port, self.app, threaded=True)
        self.port = self._httpd.server_port
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


@dataclass
class Stack:
    url: str
    rawg: _Server

    def rawg_down(self) -> None:
        """Derruba a RAWG de mentira e esvazia o cache do back-end (como após um reinício)."""
        self.rawg.stop()
        rawg_service.clear_cache()

    def rawg_up(self) -> None:
        self.rawg.start()


@pytest.fixture()
def stack(tmp_path):
    rawg = _Server(create_fake_server()).start()
    rawg_service.clear_cache()  # o cache é global ao processo; cada teste começa limpo
    app = create_app(
        {
            "SECRET_KEY": "e2e-" + "x" * 40,
            "DATABASE": str(tmp_path / "e2e.db"),
            "FRONTEND_DIST": str(DIST),
            "RATELIMIT_ENABLED": False,
            "RAWG_API_KEY": "chave-de-teste",
            "RAWG_BASE_URL": f"http://127.0.0.1:{rawg.port}/api",
            "SESSION_COOKIE_SECURE": False,
        }
    )
    web = _Server(app).start()
    try:
        yield Stack(url=f"http://127.0.0.1:{web.port}", rawg=rawg)
    finally:
        web.stop()
        rawg.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


def _fake_cover(route):
    url = route.request.url
    h = int(hashlib.md5(url.encode()).hexdigest()[:6], 16)
    hue = h % 360
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400">'
        f'<rect width="600" height="400" fill="hsl({hue},30%,26%)"/>'
        f'<circle cx="{150 + h % 300}" cy="{120 + h % 150}" r="{70 + h % 60}" fill="hsl({(hue + 40) % 360},35%,38%)"/>'
        "</svg>"
    )
    route.fulfill(status=200, content_type="image/svg+xml", body=svg)


class Client:
    """Um navegador com sua própria sessão (cookies) apontado para a pilha do teste."""

    def __init__(
        self,
        browser,
        base: str,
        width: int = 1280,
        height: int = 900,
        mobile: bool = False,
        timezone_id: str | None = None,
    ):
        self.base = base
        self.context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="pt-BR",
            is_mobile=mobile,
            has_touch=mobile,
            timezone_id=timezone_id,
        )
        self.context.route(re.compile(r"https://media\.rawg\.io/.*"), _fake_cover)
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on(
            "console",
            lambda m: self.errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None,
        )

    def open(self, path: str) -> None:
        self.page.goto(self.base + path, wait_until="networkidle")

    def close(self) -> None:
        self.context.close()


@pytest.fixture()
def make_client(browser, stack):
    clients: list[Client] = []

    def factory(**kwargs) -> Client:
        client = Client(browser, stack.url, **kwargs)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture()
def client(make_client):
    return make_client()
