"""A página inicial de quem ainda não entrou: apresentação, disco interativo, nota em discos e perfis de exemplo."""
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


def choose(client, name):
    client.page.locator(".status-picker").get_by_role("button", name=name, exact=True).click()


def test_visitante_ve_a_apresentacao_inteira(stack, client):
    client.open("/")
    page = client.page
    expect(page.get_by_role("heading", level=1)).to_have_text("O diário de quem joga.")
    for titulo in (
        "Do “quero jogar” ao “zerei”",
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


def test_o_disco_grande_joga_sozinho_ate_o_zerado_e_para(stack, client):
    client.open("/")
    expect(disc(client)).to_have_attribute("data-status", "zerado", timeout=7000)
    expect(client.page.locator(".instrument-ability[data-allowed]")).to_have_count(5)
    expect(client.page.locator(".instrument-caption")).to_contain_text("O disco fecha o círculo")


def test_mexer_no_disco_assume_o_controle_e_mostra_o_que_cada_status_libera(stack, client):
    client.open("/")
    page = client.page
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
