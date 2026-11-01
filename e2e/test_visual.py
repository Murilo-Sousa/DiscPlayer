"""Polimento visual: o que antes saía do lugar ou ficava vazio agora tem lugar e conteúdo reais."""
import re

from playwright.sync_api import expect

from helpers import api, register
from tests.fake_rawg import by_name


def gid(nome):
    return by_name(nome)["id"]


def caixa(locator):
    box = locator.bounding_box()
    assert box is not None
    return box


def preparar_ana(make_client, **kwargs):
    ana = make_client(**kwargs)
    register(ana, "Ana Souza", "ana")
    api(ana, "PUT", f"/api/library/{gid('Stardew Valley')}", {"status": "jogando", "started_at": "2026-01-10"})
    api(ana, "PUT", f"/api/library/{gid('Super Metroid')}", {"status": "quero_jogar"})
    api(ana, "PUT", f"/api/library/{gid('Hades')}", {"status": "zerado", "is_favorite": True,
                                                       "started_at": "2025-03-01", "completed_at": "2025-03-20"})
    api(ana, "POST", f"/api/games/{gid('Hades')}/reviews", {"rating": 9.5, "body": "Morrer nunca foi tão bem recompensado."})
    return ana


def test_colagem_de_capas_da_lista_cabe_na_caixa(stack, make_client):
    """Com quatro jogos, as capas empilhadas passavam da borda do cartão da lista."""
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    lista = api(ana, "POST", "/api/lists", {"title": "Quatro jogos", "is_public": True})["list"]
    for nome in ("Hades", "Celeste", "Hollow Knight", "Portal 2"):
        api(ana, "POST", f"/api/lists/{lista['id']}/games", {"rawg_id": gid(nome)})
    for largura in (1280, 390):
        c = make_client(width=largura, height=900)
        c.open("/listas")
        c.page.wait_for_selector(".cover-stack-item")
        pilha = caixa(c.page.locator(".cover-stack").first)
        capas = c.page.locator(".cover-stack-item")
        assert capas.count() == 4
        # A caixa tem 16px de margem interna: as capas ficam dentro dela, sem encostar na borda.
        esquerda, direita = pilha["x"] + 14, pilha["x"] + pilha["width"] - 14
        for indice in range(4):
            capa = caixa(capas.nth(indice))
            assert capa["x"] >= esquerda and capa["x"] + capa["width"] <= direita, f"capa {indice + 1} passa da caixa a {largura}px"


def test_inicio_de_quem_ainda_nao_entrou_mostra_o_mural_de_jogos_em_alta(stack, client):
    client.open("/")
    client.page.wait_for_selector(".cover-wall-link")
    nomes = client.page.locator(".cover-wall-name")
    assert 6 <= nomes.count() <= 15  # a RAWG de teste tem poucos jogos recentes
    primeiro = nomes.first.inner_text()
    # O mural anda devagar, e o Playwright espera o elemento parar para clicar: aqui o clique é direto.
    client.page.locator(".cover-wall-link").first.click(force=True)
    client.page.wait_for_selector(".game-title")
    assert client.page.locator(".game-title").inner_text() == primeiro


def test_inicio_logado_mostra_jogando_agora_fila_e_ranking_em_formacao(stack, make_client):
    ana = preparar_ana(make_client)
    ana.open("/")
    ana.page.wait_for_selector(".playing-card")
    cartao = ana.page.locator(".playing-card").first
    expect(cartao).to_contain_text("Stardew Valley")
    expect(cartao).to_contain_text("Desde 10 de jan de 2026")
    expect(cartao).to_contain_text(re.compile(r"\d+ dias? jogando"))
    expect(ana.page.locator(".queue")).to_contain_text("Super Metroid")
    # Uma só nota não monta ranking: a página explica a regra em vez de mostrar "10 · 1 nota".
    expect(ana.page.locator(".ranking")).to_have_count(0)
    expect(ana.page.get_by_text("O ranking ainda está se formando")).to_be_visible()
    expect(ana.page.get_by_text("3 pessoas diferentes")).to_be_visible()


def test_ranking_aparece_com_notas_de_tres_pessoas(stack, make_client):
    pessoas = []
    for nome in ("ana", "bia", "caio"):
        c = make_client()
        register(c, nome.title(), nome)
        api(c, "PUT", f"/api/library/{gid('Hades')}", {"status": "zerado"})
        api(c, "POST", f"/api/games/{gid('Hades')}/reviews", {"rating": 9})
        pessoas.append(c)
    pessoas[0].open("/")
    pessoas[0].page.wait_for_selector(".ranking-item")
    item = pessoas[0].page.locator(".ranking-item").first
    expect(item).to_contain_text("Hades")
    expect(item).to_contain_text("3 notas")


def test_descobrir_troca_entre_em_alta_e_lancamentos(stack, make_client):
    """Uma só seção com duas abas, no lugar de duas fileiras idênticas uma sobre a outra."""
    ana = preparar_ana(make_client)
    ana.open("/")
    em_alta = ana.page.get_by_role("tab", name="Em alta")
    lancamentos = ana.page.get_by_role("tab", name="Lançamentos recentes")
    em_alta.wait_for()
    assert em_alta.get_attribute("aria-selected") == "true"
    secao = ana.page.locator("section", has=ana.page.get_by_role("heading", name="Descobrir"))
    assert secao.get_by_role("link", name="Ver no catálogo").get_attribute("href") == "/jogos?ordem=popular"
    assert secao.locator(".game-card").count() == 6
    lancamentos.click()
    assert lancamentos.get_attribute("aria-selected") == "true" and em_alta.get_attribute("aria-selected") == "false"
    assert secao.get_by_role("link", name="Ver no catálogo").get_attribute("href") == "/jogos?ordem=released"
    assert secao.locator(".game-card").count() == 6
    ana.page.keyboard.press("ArrowLeft")  # teclado: as abas se movem com as setas
    assert em_alta.get_attribute("aria-selected") == "true"


def test_perfil_mostra_favoritos_e_a_ultima_review_lado_a_lado(stack, make_client):
    preparar_ana(make_client)
    c = make_client(width=1280, height=900)
    c.open("/u/ana")
    c.page.wait_for_selector(".profile-feature .section")
    secoes = c.page.locator(".profile-feature .section")
    assert secoes.count() == 2
    favoritos, review = caixa(secoes.nth(0)), caixa(secoes.nth(1))
    assert review["x"] > favoritos["x"] + favoritos["width"] - 2  # uma ao lado da outra, sem se sobrepor
    expect(secoes.nth(0)).to_contain_text("Hades")
    expect(secoes.nth(1)).to_contain_text("Morrer nunca foi tão bem recompensado.")
    expect(secoes.nth(1)).to_contain_text("Review mais recente")


def test_perfil_sem_favoritos_convida_a_dona_e_nao_mostra_nada_a_visitantes(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    api(ana, "PUT", f"/api/library/{gid('Hades')}", {"status": "jogando"})
    ana.open("/u/ana")
    expect(ana.page.get_by_text("Nenhum favorito ainda")).to_be_visible()
    visitante = make_client()
    visitante.open("/u/ana")
    visitante.page.wait_for_selector(".profile-summary")
    expect(visitante.page.get_by_text("Nenhum favorito ainda")).to_have_count(0)
    expect(visitante.page.get_by_role("heading", name="Favoritos")).to_have_count(0)


def test_retrospectiva_usa_duas_colunas_no_computador_e_uma_no_celular(stack, make_client):
    ana = preparar_ana(make_client)
    api(ana, "PUT", f"/api/library/{gid('Celeste')}", {"status": "zerado"})
    api(ana, "POST", f"/api/games/{gid('Celeste')}/reviews", {"rating": 8})
    for largura, duas in ((1280, True), (390, False)):
        c = make_client(width=largura, height=900)
        c.open("/u/ana/retrospectiva/2025")
        c.page.wait_for_selector(".retro-col")
        colunas = c.page.locator(".retro-col")
        assert colunas.count() == 2
        primeira, segunda = caixa(colunas.nth(0)), caixa(colunas.nth(1))
        lado_a_lado = segunda["x"] > primeira["x"] + primeira["width"] - 2
        assert lado_a_lado is duas, f"{largura}px"
        if duas:
            topo = c.page.locator(".retro-top").first
            expect(topo).to_contain_text("Jogo de 2025")
            expect(topo).to_contain_text("Hades")
        assert c.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_fundo_da_pagina_do_jogo_nao_atrapalha_cliques_nem_leitores_de_tela(stack, make_client):
    ana = preparar_ana(make_client)
    ana.open(f"/jogos/{gid('Hades')}")
    ana.page.wait_for_selector(".game-title")
    fundo = ana.page.locator(".game-backdrop")
    assert fundo.count() == 1
    assert fundo.get_attribute("aria-hidden") == "true" and fundo.get_attribute("alt") == ""
    assert ana.page.evaluate("getComputedStyle(document.querySelector('.game-backdrop')).pointerEvents") == "none"
    ana.page.get_by_role("button", name="Jogando").click()  # o botão por baixo da imagem continua clicável
    ana.page.wait_for_selector(".toast")


def test_celular_sem_rolagem_horizontal_nas_telas_redesenhadas(stack, make_client):
    ana = preparar_ana(make_client, width=375, height=800, mobile=True)
    visitante = make_client(width=375, height=800, mobile=True)
    caminhos = ["/", f"/jogos/{gid('Hades')}", "/u/ana", "/listas", "/diario"]
    for pessoa in (ana, visitante):
        for caminho in caminhos:
            pessoa.open(caminho)
            pessoa.page.wait_for_timeout(300)
            sobra = pessoa.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert sobra <= 0, f"{caminho} rola na horizontal em 375px (sobra {sobra}px)"
