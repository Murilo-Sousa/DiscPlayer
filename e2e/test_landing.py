"""A página inicial de quem ainda não entrou: mural de capas, disco interativo, nota em discos e perfis de exemplo."""
import re

from playwright.sync_api import expect

from helpers import register

STATUSES = {"Quero jogar": 0, "Jogando": 3, "Pausado": 3, "Abandonado": 4, "Zerado": 5}


def seed_demo(stack):
    from app import demo

    with stack.app.app_context():
        assert demo.seed()["created"] is True


def disc(client):
    return client.page.locator(".instrument-disc")


def go_to_disc(client):
    """O disco só começa a jogar quando aparece na tela."""
    client.page.locator(".instrument").scroll_into_view_if_needed()


def choose(client, name):
    client.page.locator(".status-picker").get_by_role("button", name=name, exact=True).click()


def test_visitante_ve_a_apresentacao_inteira(stack, client):
    client.open("/")
    page = client.page
    expect(page.get_by_role("heading", level=1)).to_have_text("O diário de quem joga.")
    for titulo in (
        "Do “quero jogar” ao “zerei”",
        "Veja como o diário funciona",
        "Dez pontos, cinco discos",
        "Listas para dividir o que você ama",
        "Seu ano em jogos",
        "Um diário que não faz de conta",
        "Qual foi o último jogo que você terminou?",
    ):
        expect(page.get_by_role("heading", name=titulo, level=2)).to_be_visible()
    expect(page.get_by_role("link", name="Criar meu diário").first).to_be_visible()
    # Sem ninguém na comunidade, a página convida em vez de mostrar blocos vazios, e não fala de perfis de exemplo.
    expect(page.get_by_role("heading", name="A comunidade está começando")).to_be_visible()
    expect(page.locator(".demo-badge")).to_have_count(0)
    assert client.errors == []


def test_o_topo_e_um_mural_de_capas_e_o_disco_fica_numa_secao_mais_abaixo(stack, client):
    client.open("/")
    page = client.page
    page.wait_for_selector(".cover-wall-link")
    assert 6 <= page.locator(".cover-wall-link").count() <= 15  # a RAWG de teste tem poucos jogos recentes
    assert page.locator(".cover-wall-col").count() == 3
    # os nomes só aparecem ao passar o mouse, mas cada capa tem nome para quem usa leitor de tela
    expect(page.locator(".cover-wall-name").first).to_have_css("opacity", "0")
    assert page.locator(".cover-wall-link").first.inner_text().strip() != ""
    mural = page.locator(".cover-wall").bounding_box()
    instrumento = page.locator(".instrument").bounding_box()
    assert mural["y"] + mural["height"] < instrumento["y"], "o disco deve ficar abaixo do mural"
    # passar o mouse pelo mural para as colunas (para o clique não fugir)
    page.locator(".cover-wall").hover(force=True)
    expect(page.locator(".cover-wall-col").first).to_have_css("animation-play-state", "paused")
    assert client.errors == []


def test_o_mural_anda_devagar_e_com_movimento_reduzido_fica_parado(stack, make_client):
    normal = make_client()
    normal.open("/")
    normal.page.wait_for_selector(".cover-wall-link")
    normal.page.wait_for_timeout(1500)
    assert normal.page.locator(".cover-wall-col").nth(1).evaluate("el => getComputedStyle(el).transform") != "none"
    parado = make_client(reduced_motion=True)
    parado.open("/")
    parado.page.wait_for_selector(".cover-wall-link")
    parado.page.wait_for_timeout(500)
    assert parado.page.locator(".cover-wall-col").nth(1).evaluate("el => getComputedStyle(el).transform") == "none"


def test_sem_a_rawg_o_topo_fica_so_com_o_titulo_e_o_resto_da_pagina_continua(stack, client):
    stack.rawg_down()
    try:
        client.open("/")
        page = client.page
        expect(page.get_by_role("heading", name="O diário de quem joga.", level=1)).to_be_visible()
        expect(page.locator(".landing-hero")).to_have_attribute("data-wall", "off")
        expect(page.locator(".cover-wall")).to_have_count(0)
        expect(page.get_by_role("link", name="Criar meu diário").first).to_be_visible()
        expect(page.locator(".instrument")).to_be_attached()
    finally:
        stack.rawg_up()


def test_o_disco_grande_so_comeca_a_jogar_quando_aparece_na_tela_e_vai_ate_o_zerado(stack, client):
    client.open("/")
    client.page.wait_for_selector(".cover-wall-link")
    client.page.wait_for_timeout(1500)
    expect(disc(client)).to_have_attribute("data-status", "quero_jogar")  # longe da tela, nada acontece
    go_to_disc(client)
    expect(disc(client)).to_have_attribute("data-status", "zerado", timeout=7000)
    expect(client.page.locator(".instrument-ability[data-allowed]")).to_have_count(5)
    expect(client.page.locator(".instrument-caption")).to_contain_text("O disco fecha o círculo")


def test_mexer_no_disco_assume_o_controle_e_mostra_o_que_cada_status_libera(stack, client):
    client.open("/")
    page = client.page
    go_to_disc(client)
    for nome, liberados in STATUSES.items():
        choose(client, nome)
        expect(page.locator(".instrument-ability[data-allowed]")).to_have_count(liberados)
        expect(page.locator('.status-picker button[aria-pressed="true"]')).to_have_text(nome)
    # só o zerado tem data de término; só quem começou pode dar nota
    choose(client, "Pausado")
    expect(page.locator(".instrument-ability", has_text="Data de término")).not_to_have_attribute("data-allowed", "true")
    expect(page.locator(".instrument-ability", has_text="Nota e review")).to_have_attribute("data-allowed", "true")
    choose(client, "Abandonado")
    page.wait_for_timeout(3200)  # mais que o tempo da animação de abertura: ela não pode voltar a mexer no disco
    expect(disc(client)).to_have_attribute("data-status", "abandonado")
    expect(page.locator(".instrument-ability", has_text="Jogar de novo")).to_have_attribute("data-allowed", "true")
    assert client.errors == []


def test_com_movimento_reduzido_o_disco_ja_abre_no_zerado(stack, make_client):
    c = make_client(reduced_motion=True)
    c.open("/")
    expect(disc(c)).to_have_attribute("data-status", "zerado", timeout=1500)


def test_a_nota_em_discos_responde_ao_teclado(stack, client):
    client.open("/")
    page = client.page
    secao = page.locator("section[aria-labelledby=rating-title]")
    expect(secao.locator(".rating-input-value")).to_have_text("7,5")
    secao.locator("input[type=range]").focus()
    page.keyboard.press("ArrowRight")
    expect(secao.locator(".rating-input-value")).to_have_text("8")
    expect(secao.locator(".rating-discs")).to_have_attribute("aria-label", "Nota 8 de 10")


def test_com_perfis_de_exemplo_a_pagina_mostra_reviews_ranking_listas_e_retrospectiva(stack, client):
    seed_demo(stack)
    client.open("/")
    page = client.page
    reviews = page.locator("section[aria-labelledby=community-title] .review")
    expect(reviews).to_have_count(4)
    expect(reviews.first.locator(".demo-badge")).to_have_text("Exemplo")
    expect(page.locator(".ranking-item")).not_to_have_count(0)
    expect(page.locator("section[aria-labelledby=community-title]")).to_contain_text("são fictícios")
    expect(page.locator(".landing-lists .list-card")).to_have_count(2)
    # a retrospectiva mostrada é a de um perfil de exemplo, calculada de verdade, com a marca ao lado
    link = page.get_by_role("link", name=re.compile("Ver a retrospectiva de"))
    expect(link).to_be_visible()
    expect(page.locator(".year-demo .demo-badge")).to_have_text("Exemplo")
    link.click()
    page.wait_for_url(re.compile(r"/u/[a-z_]+/retrospectiva/\d{4}$"))
    expect(page.locator(".retro-owner .demo-badge")).to_have_text("Exemplo")
    assert client.errors == []


def test_o_perfil_de_exemplo_mostra_a_marca_e_nao_aceita_login(stack, client):
    seed_demo(stack)
    client.open("/u/marina_rpg")
    expect(client.page.locator("h1.profile-name")).to_contain_text("Marina Lopes")
    expect(client.page.locator("h1.profile-name .demo-badge")).to_have_text("Exemplo")
    client.open("/entrar")
    client.page.get_by_label("E-mail ou usuário").fill("marina_rpg")
    client.page.get_by_label("Senha").fill("qualquer-senha-123")
    client.page.get_by_role("button", name="Entrar").last.click()
    expect(client.page.get_by_text("E-mail, usuário ou senha incorretos.")).to_be_visible()


def test_quem_ja_entrou_nao_ve_a_apresentacao(stack, client):
    seed_demo(stack)
    register(client, "Ana Souza", "ana")
    client.open("/")
    expect(client.page.locator(".landing")).to_have_count(0)
    expect(client.page.get_by_role("heading", name="Seu início no DiscPlayer")).to_be_attached()
    expect(client.page.locator(".home-columns").first).to_be_visible()


def test_no_celular_a_pagina_cabe_na_tela_com_e_sem_perfis_de_exemplo(stack, make_client):
    vazio = make_client(width=390, height=800, mobile=True)
    vazio.open("/")
    expect(vazio.page.locator(".instrument")).to_be_visible()
    assert vazio.page.evaluate("document.documentElement.scrollWidth") <= 391

    seed_demo(stack)
    cheio = make_client(width=390, height=800, mobile=True)
    cheio.open("/")
    cheio.page.wait_for_selector(".year-demo")
    assert cheio.page.evaluate("document.documentElement.scrollWidth") <= 391, "rolagem horizontal com a comunidade"
    cheio.page.locator(".status-picker").get_by_role("button", name="Jogando", exact=True).tap()
    expect(cheio.page.locator(".instrument-ability[data-allowed]")).to_have_count(3)
    assert vazio.errors == [] and cheio.errors == []
