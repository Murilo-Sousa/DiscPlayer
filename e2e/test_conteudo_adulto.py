"""Conteúdo adulto da RAWG: jogos 18+ não aparecem na busca nem no catálogo, a página deles é "indisponível" e não dá
para guardá-los no diário. Os jogos 18+ da RAWG simulada são fictícios (veja tests/fake_rawg.py)."""
import re

from playwright.sync_api import expect

from helpers import api, register
from tests.fake_rawg import by_name


def gid(nome):
    return by_name(nome)["id"]


def test_a_busca_e_o_catalogo_nao_mostram_jogos_18_mais(client):
    page = client.page
    client.open("/jogos")
    page.wait_for_selector("section.shelf .game-card")

    # Por nome: nada, e a contagem concorda com a tela (não diz "1 jogo" acima de uma lista vazia).
    page.get_by_label("Nome do jogo").fill("jardim proibido")
    expect(page.locator(".catalog-count")).to_have_text("Nenhum jogo encontrado.")
    expect(page.locator(".catalog-results .game-card")).to_have_count(0)

    # Um jogo comum ao lado continua aparecendo.
    page.get_by_label("Nome do jogo").fill("celeste")
    expect(page.locator(".catalog-results .game-card")).to_have_count(1)

    # A pesquisa do topo também.
    client.open("/buscar?q=noite sem censura")
    expect(page.get_by_text("Nada encontrado para “noite sem censura”")).to_be_visible()
    expect(page.get_by_text("Noite Sem Censura", exact=True)).to_have_count(0)
    assert client.errors == []


def test_o_endereco_de_um_jogo_18_mais_mostra_jogo_indisponivel(client):
    for nome in ("Jardim Proibido", "Noite Sem Censura"):
        client.open(f"/jogos/{gid(nome)}")
        expect(client.page.get_by_role("heading", name="Jogo indisponível", level=1)).to_be_visible()
        expect(client.page.get_by_text("conteúdo adulto")).to_be_visible()
        expect(client.page.locator(".game-title")).to_have_count(0)  # nada da ficha do jogo
        expect(client.page).to_have_title(re.compile(r"^Jogo indisponível"))
    # Um jogo que não existe continua sendo "não encontrado", não "indisponível".
    client.open("/jogos/123")
    expect(client.page.get_by_role("heading", name="Jogo não encontrado", level=1)).to_be_visible()
    # (os 404 dessas páginas aparecem no console do navegador como "Failed to load resource": são esperados)
    assert all("404" in erro for erro in client.errors), client.errors


def test_um_jogo_18_mais_nao_entra_no_diario_nem_pela_api(client):
    register(client, "Ana", "ana")
    request = client.context.request
    token = request.get(f"{client.base}/api/auth/me").json()["csrf_token"]
    resposta = request.fetch(
        f"{client.base}/api/library/{gid('Jardim Proibido')}",
        method="PUT",
        data={"status": "quero_jogar"},
        headers={"X-CSRF-Token": token},
    )
    assert resposta.status == 404
    assert resposta.json()["error"]["code"] == "game_blocked"
    # Nada ficou no diário.
    client.open("/u/ana")
    expect(client.page.locator(".game-card")).to_have_count(0)


def test_o_resto_do_catalogo_segue_igual(stack, client):
    """Um jogo 17+ comum (o filtro padrão é o "explicit") abre normalmente."""
    register(client, "Ana", "ana")
    client.open(f"/jogos/{gid('The Witcher 3: Wild Hunt')}")
    expect(client.page.locator(".game-title")).to_have_text("The Witcher 3: Wild Hunt")
    assert api(client, "GET", "/api/health")["adult_content_filter"] == "explicit"
