"""A repaginada dos jogos: catálogo com prateleiras, filtros em chips, cards com o diário e a média da comunidade,
atalho "guardar na fila", e a página do jogo com barra de status no celular e "mais jogos do gênero"."""
import re

from playwright.sync_api import expect

from helpers import api, open_game, register
from tests.fake_rawg import by_name


def gid(nome):
    return by_name(nome)["id"]


def seed_demo(stack):
    from app import demo

    with stack.app.app_context():
        assert demo.seed()["created"] is True


def prateleira(page, titulo):
    return page.locator("section.shelf").filter(has=page.get_by_role("heading", name=titulo, level=2))


def card(page, nome):
    """O card pelo título (o nome acessível do link começa pelo status quando o jogo está no diário)."""
    titulo = page.locator(".game-card-title").filter(has_text=re.compile(rf"^{re.escape(nome)}$"))
    return page.locator(".game-card").filter(has=titulo).first


# ----------------------------------------------------------------------------- prateleiras e busca
def test_o_catalogo_abre_com_prateleiras_e_a_busca_troca_por_resultados(stack, client):
    seed_demo(stack)
    client.open("/jogos")
    page = client.page
    page.wait_for_selector("section.shelf .game-card")
    for titulo in ("Em alta", "Lançamentos recentes", "Mais bem avaliados no DiscPlayer"):
        expect(prateleira(page, titulo)).to_be_visible()
    expect(page.get_by_role("heading", name="Todos os jogos", level=2)).to_be_visible()

    page.get_by_label("Nome do jogo").fill("celeste")
    expect(page.locator("section.shelf")).to_have_count(0)  # com busca, só resultados
    expect(page.get_by_role("heading", name="Todos os jogos")).to_have_count(0)
    expect(page.locator(".catalog-results .game-card")).to_have_count(1)

    page.get_by_role("button", name="Limpar tudo").click()
    expect(prateleira(page, "Em alta")).to_be_visible()
    expect(page.get_by_label("Nome do jogo")).to_have_value("")
    assert client.errors == []


def test_sem_notas_da_comunidade_nao_ha_prateleira_de_melhores_nem_bloco_vazio(stack, client):
    client.open("/jogos")
    client.page.wait_for_selector("section.shelf .game-card")
    expect(prateleira(client.page, "Em alta")).to_be_visible()
    expect(client.page.get_by_role("heading", name="Mais bem avaliados no DiscPlayer")).to_have_count(0)
    expect(client.page.locator(".game-card-community")).to_have_count(0)  # ninguém avaliou nada ainda


def test_ver_todos_dos_lancamentos_abre_o_catalogo_ordenado_por_lancamento(stack, client):
    client.open("/jogos")
    page = client.page
    prateleira(page, "Lançamentos recentes").get_by_role("link", name="Ver todos").click()
    expect(page).to_have_url(re.compile(r"/jogos\?ordem=released$"))
    expect(page.get_by_role("button", name="Remover o filtro Ordem: Lançamento mais recente")).to_be_visible()
    page.wait_for_selector(".catalog-results .game-card")
    datas = page.locator(".catalog-results .game-card-meta").all_inner_texts()
    anos = [int(texto[:4]) for texto in datas]
    assert anos == sorted(anos, reverse=True)


# ----------------------------------------------------------------------------- filtros
def test_chip_de_genero_filtra_pela_url_e_clicar_de_novo_tira(stack, client):
    client.open("/jogos")
    page = client.page
    page.wait_for_selector(".genre-chip")
    rpg = page.get_by_role("button", name="RPG", exact=True)
    todos = page.get_by_role("button", name="Todos", exact=True)
    expect(todos).to_have_attribute("aria-pressed", "true")
    rpg.click()
    expect(page).to_have_url(re.compile(r"genero=rpg"))
    expect(rpg).to_have_attribute("aria-pressed", "true")
    expect(todos).to_have_attribute("aria-pressed", "false")
    page.wait_for_selector(".catalog-results .game-card")
    expect(page.locator("section.shelf")).to_have_count(0)
    rpg.click()
    expect(page).not_to_have_url(re.compile(r"genero="))
    expect(todos).to_have_attribute("aria-pressed", "true")
    expect(prateleira(page, "Em alta")).to_be_visible()


def test_o_painel_de_filtros_abre_conta_os_filtros_e_os_chips_tiram_um_a_um(stack, client):
    client.open("/jogos")
    page = client.page
    painel = page.locator("#catalog-filters")
    botao = page.get_by_role("button", name=re.compile("^Filtros"))
    expect(painel).to_be_hidden()
    expect(botao).to_have_attribute("aria-expanded", "false")
    botao.click()
    expect(painel).to_be_visible()
    expect(botao).to_have_attribute("aria-expanded", "true")

    page.get_by_label("Plataforma").select_option(label="PC")
    page.get_by_label("Ano de lançamento").select_option("2018")
    expect(page).to_have_url(re.compile(r"plataforma=1"))
    expect(page).to_have_url(re.compile(r"ano=2018"))
    expect(botao).to_contain_text("2")  # dois filtros do painel ativos
    expect(page.get_by_role("button", name="Remover o filtro Plataforma: PC")).to_be_visible()
    expect(page.get_by_role("button", name="Remover o filtro Ano: 2018")).to_be_visible()
    page.wait_for_selector(".catalog-results .game-card")

    page.get_by_role("button", name="Remover o filtro Ano: 2018").click()
    expect(page).not_to_have_url(re.compile(r"ano="))
    expect(page).to_have_url(re.compile(r"plataforma=1"))
    expect(botao).to_contain_text("1")

    page.get_by_role("button", name="Limpar tudo").click()
    expect(page).to_have_url(re.compile(r"/jogos$"))
    expect(page.locator(".filter-chips")).to_have_count(0)
    assert client.errors == []


def test_filtros_na_url_abrem_o_catalogo_ja_filtrado_e_sem_resultado_oferece_limpar(stack, client):
    client.open("/jogos?genero=rpg&ano=1990")
    page = client.page
    expect(page.get_by_text("Nenhum jogo com esses filtros")).to_be_visible()
    page.get_by_role("button", name="Limpar filtros").click()
    expect(page).to_have_url(re.compile(r"/jogos$"))
    page.wait_for_selector("section.shelf .game-card")


# ----------------------------------------------------------------------------- média e diário nos cards
def test_cards_mostram_a_media_da_comunidade_com_o_numero_de_notas(stack, client):
    seed_demo(stack)
    client.open("/jogos")
    client.page.wait_for_selector("section.shelf .game-card")
    lista = api(client, "GET", "/api/games?per_page=40")["results"]
    avaliado = next(game for game in lista if game["community"])
    sem_nota = next(game for game in lista if not game["community"])
    comunidade = avaliado["community"]
    media = f"{round(comunidade['average'], 2):g}".replace(".", ",")  # o mesmo arredondamento da interface

    page = client.page
    client.open(f"/jogos?q={avaliado['name']}")
    page.wait_for_selector(".game-card")
    linha = card(page, avaliado["name"]).locator(".game-card-community")
    expect(linha.locator("strong")).to_have_text(media)
    expect(linha.locator(".game-card-count")).to_have_text(f"({comunidade['count']})")
    expect(linha.locator(".sr-only")).to_contain_text("no DiscPlayer")

    # um jogo que ninguém avaliou não ganha linha de média
    client.open(f"/jogos?q={sem_nota['name']}")
    page.wait_for_selector(".game-card")
    expect(card(page, sem_nota["name"]).locator(".game-card-community")).to_have_count(0)


def test_visitante_nao_ve_o_botao_de_guardar_na_fila(stack, client):
    client.open("/jogos")
    client.page.wait_for_selector(".game-card")
    expect(client.page.locator(".game-card-add")).to_have_count(0)
    expect(client.page.locator(".game-card-flags")).to_have_count(0)


def test_o_card_mostra_o_status_de_quem_ja_tem_o_jogo_e_guarda_na_fila_quem_nao_tem(stack, client):
    register(client, "Ana Souza", "ana")
    api(client, "PUT", f"/api/library/{gid('Hollow Knight')}", {"status": "jogando"})
    client.open("/jogos?q=knight")
    page = client.page
    page.wait_for_selector(".game-card")
    knight = card(page, "Hollow Knight")
    expect(knight.locator(".game-card-flags")).to_contain_text("Jogando")
    expect(knight.locator(".game-card-add")).to_have_count(0)  # já está no diário: nada de atalho

    client.open("/jogos?q=celeste")
    page.wait_for_selector(".game-card")
    celeste = card(page, "Celeste")
    celeste.hover()
    celeste.get_by_role("button", name="Guardar Celeste em Quero jogar").click()
    expect(page.locator(".toast")).to_contain_text("“Celeste” está na sua fila.")
    expect(celeste.locator(".game-card-flags")).to_contain_text("Quero jogar")
    expect(celeste.locator(".game-card-add")).to_have_count(0)
    entrada = api(client, "GET", f"/api/games/{gid('Celeste')}")["viewer"]["entry"]
    assert entrada["status"] == "quero_jogar" and entrada["started_at"] is None and entrada["completed_at"] is None
    # o diário mostra o jogo na fila, e a página recarregada continua sabendo
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".game-card")
    expect(card(page, "Celeste").locator(".game-card-flags")).to_contain_text("Quero jogar")
    assert client.errors == []


def test_o_atalho_nunca_mexe_num_jogo_que_entrou_no_diario_depois_que_a_pagina_abriu(stack, client):
    register(client, "Ana Souza", "ana")
    client.open("/jogos?q=celeste")
    page = client.page
    page.wait_for_selector(".game-card")
    celeste = card(page, "Celeste")
    celeste.hover()
    expect(celeste.get_by_role("button", name="Guardar Celeste em Quero jogar")).to_be_visible()
    # em outra aba, a pessoa já tinha começado o jogo
    api(client, "PUT", f"/api/library/{gid('Celeste')}", {"status": "jogando"})
    celeste.get_by_role("button", name="Guardar Celeste em Quero jogar").click()
    expect(page.locator(".toast").last).to_contain_text("já estava no seu diário")
    expect(celeste.locator(".game-card-flags")).to_contain_text("Jogando")  # o cartão se corrige
    expect(celeste.locator(".game-card-add")).to_have_count(0)
    entrada = api(client, "GET", f"/api/games/{gid('Celeste')}")["viewer"]["entry"]
    assert entrada["status"] == "jogando"  # não voltou para a fila


# ----------------------------------------------------------------------------- página do jogo
def test_a_pagina_do_jogo_sugere_mais_jogos_do_mesmo_genero(stack, client):
    titulo = open_game(client, "minecraft")
    page = client.page
    page.wait_for_selector(".game-related .game-card")
    secao = page.locator(".game-related")
    expect(secao.get_by_role("heading", level=2)).to_have_text(re.compile(r"^Mais em .+"))
    nomes = secao.locator(".game-card-title").all_inner_texts()
    assert nomes and titulo not in nomes  # o próprio jogo fica de fora
    link = secao.get_by_role("link", name="Ver todos")
    assert re.search(r"^/jogos\?genero=[a-z0-9-]+$", link.get_attribute("href"))
    link.click()
    expect(page).to_have_url(re.compile(r"/jogos\?genero="))
    page.wait_for_selector(".catalog-results .game-card")


def test_na_prateleira_do_jogo_o_atalho_guarda_na_fila(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    page = client.page
    page.wait_for_selector(".game-related .game-card")
    primeiro = page.locator(".game-related .game-card").first
    nome = primeiro.locator(".game-card-title").inner_text()
    primeiro.hover()
    primeiro.get_by_role("button", name=f"Guardar {nome} em Quero jogar").click()
    expect(page.locator(".toast")).to_contain_text(f"“{nome}” está na sua fila.")
    expect(primeiro.locator(".game-card-flags")).to_contain_text("Quero jogar")


def test_no_computador_nao_ha_barra_de_status_fixa(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    client.page.wait_for_selector(".game-related .game-card")
    client.page.wait_for_timeout(500)
    expect(client.page.locator(".status-dock")).to_have_count(0)  # o painel do diário já está à vista


def test_no_celular_a_barra_fixa_leva_ao_painel_do_diario_e_acompanha_o_status(stack, make_client):
    c = make_client(width=390, height=800, mobile=True)
    register(c, "Bia Lima", "bia")
    open_game(c, "minecraft")
    page = c.page
    dock = page.locator(".status-dock")
    expect(dock).to_be_visible()
    expect(dock).to_contain_text("Fora do seu diário")

    dock.get_by_role("button", name="Registrar").click()
    expect(dock).to_have_count(0)  # o painel chegou à tela: a barra sai
    expect(page.locator(".status-option").first).to_be_focused()
    page.locator(".status-picker").get_by_role("button", name="Jogando", exact=True).tap()
    page.wait_for_selector('.status-picker button[aria-pressed="true"]:has-text("Jogando")')

    page.evaluate("window.scrollTo(0, 0)")
    expect(dock).to_be_visible()
    expect(dock).to_contain_text("Jogando")
    expect(dock.get_by_role("button", name="Mudar status")).to_be_visible()

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    expect(dock).to_have_count(0)  # no fim da página o rodapé aparece, e a barra não cobre os links dele
    assert c.errors == []


def test_no_celular_o_visitante_ve_um_convite_para_entrar_na_barra(stack, make_client):
    c = make_client(width=390, height=800, mobile=True)
    open_game(c, "minecraft")
    dock = c.page.locator(".status-dock")
    expect(dock).to_be_visible()
    expect(dock).to_contain_text("Quer registrar este jogo?")
    assert re.search(r"^/entrar\?proximo=%2Fjogos%2F", dock.get_by_role("link", name="Entrar").get_attribute("href"))


# ----------------------------------------------------------------------------- celular
def test_no_celular_o_catalogo_cabe_na_tela_e_o_painel_de_filtros_abre(stack, make_client):
    seed_demo(stack)
    c = make_client(width=390, height=800, mobile=True)
    c.open("/jogos")
    page = c.page
    page.wait_for_selector("section.shelf .game-card")
    assert page.evaluate("document.documentElement.scrollWidth") <= 391
    # o primeiro jogo já aparece na primeira tela (antes, os filtros ocupavam quase tudo)
    topo = page.locator("section.shelf .game-card").first.bounding_box()["y"]
    assert topo < 800, topo
    page.get_by_role("button", name=re.compile("^Filtros")).tap()
    expect(page.locator("#catalog-filters")).to_be_visible()
    page.get_by_label("Ordenar por").select_option(label="Nome (A–Z)")
    expect(page).to_have_url(re.compile(r"ordem=name"))
    assert page.evaluate("document.documentElement.scrollWidth") <= 391
    assert c.errors == []
