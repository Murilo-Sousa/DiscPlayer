"""Gestos reutilizados pelos testes (sempre pela interface, como uma pessoa faria)."""
from __future__ import annotations

import re

PASSWORD = "segredo-longo-123"


def register(client, display_name: str, username: str, email: str | None = None) -> None:
    page = client.page
    client.open("/cadastro")
    page.get_by_label("Nome de exibição (opcional)").fill(display_name)
    page.get_by_label("Nome de usuário").fill(username)
    page.get_by_label("E-mail").fill(email or f"{username}@example.com")
    page.get_by_label("Senha").fill(PASSWORD)
    page.get_by_role("button", name="Criar conta").last.click()
    page.wait_for_url(re.compile(r"/jogos$"))
    page.wait_for_selector(".user-menu-button")


def login(client, identifier: str, password: str = PASSWORD) -> None:
    page = client.page
    page.get_by_label("E-mail ou usuário").fill(identifier)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Entrar").last.click()


def open_game(client, name_query: str) -> str:
    """Procura pelo nome no catálogo, abre o primeiro resultado e devolve o título."""
    page = client.page
    client.open(f"/jogos?q={name_query}")
    page.wait_for_selector(".game-card")
    page.locator(".game-card-link").first.click()
    page.wait_for_selector(".game-title")
    return page.locator(".game-title").inner_text()


def set_rating(client, steps_right: int) -> None:
    """A nota começa em 5 ao tocar no controle; cada seta para a direita soma 0,5."""
    slider = client.page.locator("input[type=range]")
    slider.focus()
    for _ in range(steps_right):
        client.page.keyboard.press("ArrowRight")


def toast_text(client) -> str:
    client.page.wait_for_selector(".toast")
    return client.page.locator(".toast").last.inner_text()
