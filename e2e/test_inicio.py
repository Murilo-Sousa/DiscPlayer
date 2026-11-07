"""O início de quem está logado: quem joga o quê agora e as novidades agrupadas, de quem se segue ou da comunidade."""
import re

from playwright.sync_api import expect

from helpers import api, login, register
from tests.fake_igdb import by_name


def gid(nome):
    return by_name(nome)["id"]


def cenario(make_client, **kwargs):
    """Ana segue Bia, Caio e Duda. A Eva joga e cria listas, mas a Ana não a segue."""
    ana = make_client(**kwargs)
    register(ana, "Ana Souza", "ana")
    gente = {}
    for nome, usuario in (("Bia Lima", "bia"), ("Caio Dias", "caio"), ("Duda Reis", "duda"), ("Eva Prado", "eva")):
        cliente = make_client()
        register(cliente, nome, usuario)
        gente[usuario] = cliente
    hades = gid("Hades")
    api(gente["bia"], "PUT", f"/api/library/{hades}", {"status": "zerado", "is_favorite": True})
    api(gente["bia"], "POST", f"/api/games/{hades}/reviews", {"rating": 9.5, "body": "Morrer nunca foi tão bem recompensado."})
    api(gente["bia"], "PUT", f"/api/library/{gid('Stardew Valley')}", {"status": "jogando", "started_at": "2026-10-10"})
    api(gente["caio"], "PUT", f"/api/library/{gid('Celeste')}", {"status": "jogando", "started_at": "2026-10-29"})
    api(gente["caio"], "PUT", f"/api/library/{gid('Hollow Knight')}", {"status": "jogando", "started_at": "2026-11-01"})
    api(gente["caio"], "PUT", f"/api/library/{gid('Portal 2')}", {"status": "abandonado"})
    for nome in ("Hades", "Celeste", "Super Metroid", "Minecraft"):
        api(gente["duda"], "PUT", f"/api/library/{gid(nome)}", {"status": "quero_jogar"})
    api(gente["duda"], "PUT", f"/api/library/{gid('Portal 2')}", {"status": "jogando", "started_at": "2026-09-01"})
    lista = api(gente["eva"], "POST", "/api/lists", {"title": "Roguelikes da madrugada", "is_public": True})["list"]
    for nome in ("Hades", "Celeste", "Hollow Knight"):
        api(gente["eva"], "POST", f"/api/lists/{lista['id']}/games", {"igdb_id": gid(nome)})
    api(gente["eva"], "PUT", f"/api/library/{gid('Minecraft')}", {"status": "jogando"})
    api(ana, "PUT", f"/api/library/{gid('Super Metroid')}", {"status": "jogando"})  # o jogo de quem vê não aparece
    for usuario in ("bia", "caio", "duda"):
        api(ana, "PUT", f"/api/users/{usuario}/follow")
    return ana


def cartao(page, pessoa):
    return page.locator(".player-card").filter(has=page.get_by_role("link", name=pessoa, exact=True))


def esperar_inicio(client):
    client.page.wait_for_selector(".player-card")
    client.page.wait_for_selector(".news-item")


def test_o_inicio_mostra_quem_joga_o_que_e_as_novidades_agrupadas(stack, make_client):
    ana = cenario(make_client)
    page = ana.page
    ana.open("/")
    esperar_inicio(ana)
    expect(page.get_by_role("heading", name="Jogando agora")).to_be_visible()
    expect(page.get_by_role("heading", name="Novidades")).to_be_visible()
    for titulo in ("Na sua fila", "Na comunidade"):
        expect(page.get_by_role("heading", name=titulo)).to_have_count(0)  # o diário pessoal fica no diário

    # um cartão por pessoa seguida, com o jogo que começou há menos tempo
    expect(page.locator(".player-card")).to_have_count(3)
    caio = cartao(page, "Caio Dias")
    expect(caio).to_contain_text("Hollow Knight")
    expect(caio).to_contain_text("+1 jogo")
    expect(caio).to_contain_text(re.compile(r"Começou hoje|\d+ dias? jogando"))
    expect(cartao(page, "Duda Reis")).to_contain_text("Portal 2")
    expect(cartao(page, "Bia Lima")).to_contain_text("Stardew Valley")
    expect(page.locator(".home-playing")).not_to_contain_text("Eva Prado")  # a Ana não a segue
    expect(page.locator(".home-playing")).not_to_contain_text("Ana Souza")  # nem o próprio jogo

    # as novidades vêm agrupadas: três cartões, e "começou a jogar" não é novidade
    novidades = page.locator(".news-item")
    expect(novidades).to_have_count(3)
    fila = novidades.filter(has_text="Duda Reis")
    expect(fila).to_contain_text("guardou 4 jogos na fila")
    expect(fila.locator(".news-mini")).to_have_count(4)
    expect(novidades.filter(has_text="Caio Dias")).to_contain_text("abandonou Portal 2")
    zerou = novidades.filter(has_text="Bia Lima")
    expect(zerou).to_contain_text("zerou Hades")
    expect(zerou.locator(".news-rating")).to_have_text("9,5")
    expect(zerou).to_contain_text("Morrer nunca foi tão bem recompensado.")
    expect(page.locator(".news-item", has_text="avaliou")).to_have_count(0)  # zerou e avaliou: um cartão só

    # o ranking só aparece com notas de três pessoas
    expect(page.locator(".ranking")).to_have_count(0)
    expect(page.get_by_text("O ranking ainda está se formando")).to_be_visible()
    assert ana.errors == []


def test_clicar_no_cartao_leva_ao_jogo_e_ao_perfil(stack, make_client):
    ana = cenario(make_client)
    page = ana.page
    ana.open("/")
    esperar_inicio(ana)
    cartao(page, "Caio Dias").get_by_role("link", name="Hollow Knight").click()
    page.wait_for_selector(".game-title")
    assert page.locator(".game-title").inner_text() == "Hollow Knight"
    ana.open("/")
    esperar_inicio(ana)
    cartao(page, "Bia Lima").get_by_role("link", name="Bia Lima").click()
    expect(page).to_have_url(re.compile(r"/u/bia$"))


def test_o_seletor_troca_para_a_comunidade_nas_duas_partes_e_lembra_a_escolha(stack, make_client):
    ana = cenario(make_client)
    page = ana.page
    ana.open("/")
    esperar_inicio(ana)
    seguidos = page.get_by_role("button", name="Quem eu sigo", exact=True)
    comunidade = page.get_by_role("button", name="Comunidade", exact=True)
    expect(seguidos).to_have_attribute("aria-pressed", "true")
    expect(comunidade).to_have_attribute("aria-pressed", "false")

    comunidade.click()
    expect(comunidade).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".player-card")).to_have_count(4)  # agora com a Eva
    expect(cartao(page, "Eva Prado")).to_contain_text("Minecraft")
    expect(page.locator(".news-item").filter(has_text="Roguelikes da madrugada")).to_contain_text("criou a lista")
    expect(page.locator(".news-item").filter(has_text="Roguelikes da madrugada")).to_contain_text("3 jogos")

    page.reload(wait_until="networkidle")  # a escolha fica guardada neste navegador
    expect(page.get_by_role("button", name="Comunidade", exact=True)).to_have_attribute("aria-pressed", "true")
    page.wait_for_selector(".player-card")
    expect(page.locator(".player-card")).to_have_count(4)

    page.get_by_role("button", name="Quem eu sigo", exact=True).click()
    expect(page.locator(".player-card")).to_have_count(3)
    assert ana.errors == []


def test_quem_nao_segue_ninguem_comeca_na_comunidade(stack, make_client):
    cenario(make_client)
    nova = make_client()
    register(nova, "Fabi Costa", "fabi")
    page = nova.page
    nova.open("/")
    expect(page.get_by_role("button", name="Comunidade", exact=True)).to_have_attribute("aria-pressed", "true")
    page.wait_for_selector(".player-card")
    expect(page.locator(".player-card")).to_have_count(5)  # Ana, Bia, Caio, Duda e Eva: para a Fabi, a Ana também é "comunidade"
    # quem escolhe "Quem eu sigo" sem seguir ninguém recebe o convite, e não uma tela vazia
    page.get_by_role("button", name="Quem eu sigo", exact=True).click()
    expect(page.get_by_text("Você ainda não segue ninguém")).to_be_visible()
    expect(page.get_by_role("link", name="Procurar jogadores")).to_have_attribute("href", "/buscar")
    expect(page.get_by_text("Siga outras pessoas para ver aqui o que elas zeram, avaliam e listam.")).to_be_visible()
    page.get_by_role("button", name="Ver a comunidade").click()
    expect(page.get_by_role("button", name="Comunidade", exact=True)).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".player-card")).to_have_count(5)


def test_sem_ninguem_jogando_os_avisos_ocupam_o_lugar_da_fileira(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    ana.open("/")
    page = ana.page
    expect(page.get_by_text("Ninguém está jogando agora")).to_be_visible()
    expect(page.get_by_text("Nada de novo por aqui")).to_be_visible()
    expect(page.get_by_role("button", name="Quem eu sigo", exact=True)).to_be_visible()  # o seletor continua à mão
    assert page.locator(".player-card").count() == 0
    assert ana.errors == []


def test_no_celular_a_fileira_rola_de_lado_e_a_pagina_nao(stack, make_client):
    cenario(make_client)
    celular = make_client(width=390, height=900, mobile=True)
    celular.open("/entrar")
    login(celular, "ana")
    celular.page.wait_for_selector(".user-menu-button")
    celular.open("/")
    esperar_inicio(celular)
    page = celular.page
    assert page.evaluate("document.documentElement.scrollWidth") <= 391
    trilho = page.locator(".home-playing .shelf-track")
    assert trilho.evaluate("node => node.scrollWidth > node.clientWidth")  # os três cartões passam da largura da tela
    topo = page.locator(".home-playing .player-card").first.bounding_box()
    assert topo["y"] < 400  # o primeiro cartão já aparece na primeira tela
    expect(page.locator(".news-item").first).to_be_visible()
    assert celular.errors == []
