"""Retrospectiva do ano e prévia de links, pela interface e pelo HTML que um robô (WhatsApp, Discord) lê."""
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from playwright.sync_api import expect

from helpers import api, register, toast_text
from tests.fake_rawg import by_name

HADES = by_name("Hades")["id"]
CELESTE = by_name("Celeste")["id"]
HOLLOW = by_name("Hollow Knight")["id"]
ANO_ATUAL = datetime.now(timezone.utc).year  # o servidor conta o ano em UTC


def zerar(client, rawg_id, inicio, fim):
    api(client, "PUT", f"/api/library/{rawg_id}", {"status": "zerado", "started_at": inicio, "completed_at": fim})


def preparar_ana(make_client):
    """Ana: dois zerados em 2025 (um com nota 9,5) e um em 2024. As datas passadas só vêm pela API."""
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    zerar(ana, HADES, "2025-03-01", "2025-03-20")
    zerar(ana, CELESTE, "2025-05-01", "2025-05-04")
    zerar(ana, HOLLOW, "2024-02-01", "2024-02-10")
    api(ana, "POST", f"/api/games/{HADES}/reviews", {"rating": 9.5})
    return ana


class Cabecalho(HTMLParser):
    def __init__(self, texto):
        super().__init__()
        self.titulos, self.metas = [], {}
        self._dentro = False
        self.feed(texto)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._dentro = True
            self.titulos.append("")
        elif tag == "meta":
            nome = attrs.get("property") or attrs.get("name")
            if nome:
                self.metas.setdefault(nome, []).append(attrs.get("content", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self._dentro = False

    def handle_data(self, data):
        if self._dentro:
            self.titulos[-1] += data


def cabecalho(client, caminho):
    resposta = client.context.request.get(client.base + caminho)
    assert resposta.ok
    return Cabecalho(resposta.text())


# ------------------------------------------------------------------- página
def test_do_perfil_a_retrospectiva_com_numeros_reais(stack, make_client):
    ana = preparar_ana(make_client)
    page = ana.page
    ana.open("/u/ana")
    page.get_by_role("link", name="Retrospectiva").click()
    page.wait_for_url(re.compile(r"/u/ana/retrospectiva$"))
    # A nota foi dada hoje, então o último ano com registros é o atual: em andamento e sem jogos zerados nele.
    expect(page.get_by_role("heading", level=1)).to_contain_text(f"Retrospectiva {ANO_ATUAL}")
    expect(page.get_by_text(f"{ANO_ATUAL} ainda está em andamento")).to_be_visible()
    expect(page.get_by_text(f"Nenhum jogo zerado em {ANO_ATUAL}.")).to_be_visible()
    expect(page.locator(".retro-big-number")).to_have_count(0)  # nada de número grande inventado
    expect(page.get_by_role("heading", name="Notas dadas")).to_be_visible()

    page.get_by_role("navigation", name="Anos com registros").get_by_role("link", name="2025").click()
    expect(page.get_by_role("heading", level=1)).to_contain_text("Retrospectiva 2025")
    expect(page.locator(".retro-big-number")).to_have_text("2")
    expect(page.locator(".retro-big-label")).to_have_text("jogos zerados")
    expect(page.get_by_role("heading", name="Jogo de 2025")).to_be_visible()
    expect(page.locator(".retro-goty-name")).to_have_text("Hades")  # a única nota
    expect(page.locator(".retro-goty")).to_contain_text("Zerado em 20 de mar de 2025")
    # Gráfico por mês: março e maio, em tabela para leitores de tela.
    tabela = page.locator(".histogram .sr-only table").first
    expect(tabela.get_by_role("row", name=re.compile("março"))).to_contain_text("1")
    expect(tabela.get_by_role("row", name=re.compile("maio"))).to_contain_text("1")
    expect(page.get_by_text("Mês mais cheio: março, com 1 zerado.")).to_be_visible()
    # Ritmo: dois zerados com as duas datas.
    expect(page.get_by_role("heading", name="Ritmo")).to_be_visible()
    expect(page.locator(".stat", has_text="Mais rápido")).to_contain_text("3 dias")
    expect(page.locator(".stat", has_text="Mais longo")).to_contain_text("19 dias")
    assert ana.errors == []


def test_navegar_entre_anos_e_ano_sem_registros(stack, make_client):
    ana = preparar_ana(make_client)
    page = ana.page
    ana.open("/u/ana/retrospectiva/2025")
    nav = page.get_by_role("navigation", name="Anos com registros")
    expect(nav.get_by_role("link", name="2025")).to_have_attribute("aria-current", "page")
    nav.get_by_role("link", name="2024").click()
    page.wait_for_url(re.compile(r"/retrospectiva/2024$"))
    expect(page.get_by_role("heading", level=1)).to_contain_text("2024")
    expect(page.locator(".retro-big-number")).to_have_text("1")
    expect(page.get_by_role("link", name="Hollow Knight").first).to_be_visible()

    ana.open("/u/ana/retrospectiva/2019")
    expect(page.get_by_role("heading", name="Nada registrado em 2019")).to_be_visible()
    expect(page.get_by_text("Quando você registrar jogos")).to_be_visible()
    expect(page.get_by_role("button", name="Compartilhar")).to_have_count(0)  # nada para compartilhar
    page.get_by_role("navigation", name="Anos com registros").get_by_role("link", name="2025").click()
    expect(page.locator(".retro-big-number")).to_have_text("2")


def test_visitante_ve_a_retrospectiva_sem_dados_privados(stack, make_client):
    ana = preparar_ana(make_client)
    api(ana, "POST", "/api/lists", {"title": "SEGREDO-DA-ANA", "is_public": False})
    visitante = make_client()
    visitante.open("/u/ana/retrospectiva/2025")
    page = visitante.page
    expect(page.locator(".retro-big-number")).to_have_text("2")
    expect(page.get_by_role("button", name="Compartilhar")).to_be_visible()  # qualquer pessoa pode compartilhar
    assert "SEGREDO-DA-ANA" not in page.content()
    assert "ana@example.com" not in page.content()
    assert visitante.errors == []


def test_enderecos_invalidos_mostram_nao_encontrado(stack, make_client):
    ana = preparar_ana(make_client)
    for caminho in ("/u/ninguem/retrospectiva", "/u/ana/retrospectiva/abc", "/u/ana/retrospectiva/1999", "/u/ana/retrospectiva/20255"):
        ana.open(caminho)
        expect(ana.page.get_by_role("heading", name="Retrospectiva não encontrada")).to_be_visible()


def test_diario_leva_a_retrospectiva(stack, make_client):
    ana = preparar_ana(make_client)
    ana.open("/diario")
    ana.page.get_by_role("link", name="Minha retrospectiva").click()
    ana.page.wait_for_url(re.compile(r"/u/ana/retrospectiva$"))
    expect(ana.page.get_by_role("heading", level=1)).to_contain_text("Retrospectiva")


# ------------------------------------------------------------------- compartilhar
def test_compartilhar_copia_o_endereco_com_o_ano(stack, make_client):
    ana = preparar_ana(make_client)
    ana.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ana.base)
    ana.open("/u/ana/retrospectiva")  # sem ano na barra: o link copiado já leva o ano
    ana.page.get_by_role("button", name="Compartilhar").click()
    assert "Endereço copiado" in toast_text(ana)
    assert ana.page.evaluate("navigator.clipboard.readText()") == f"{ana.base}/u/ana/retrospectiva/{ANO_ATUAL}"


def test_imagem_de_compartilhamento_carrega_e_pode_ser_baixada(stack, make_client):
    ana = preparar_ana(make_client)
    ana.open("/u/ana/retrospectiva/2025")
    page = ana.page
    imagem = page.locator(".retro-card img")
    imagem.scroll_into_view_if_needed()
    page.wait_for_function("document.querySelector('.retro-card img').complete")
    assert imagem.evaluate("img => img.naturalWidth") == 1200 and imagem.evaluate("img => img.naturalHeight") == 630
    with page.expect_download() as download:
        page.get_by_role("link", name="Baixar imagem").click()
    assert download.value.suggested_filename == "retrospectiva-2025-ana.png"
    resposta = ana.context.request.get(f"{ana.base}/api/share/retrospective/ana/2025.png")
    assert resposta.headers["content-type"] == "image/png" and resposta.body().startswith(b"\x89PNG")
    assert ana.errors == []


# ------------------------------------------------------------------- prévia de links (HTML que o robô lê)
def test_html_da_retrospectiva_tem_a_previa_pronta_sem_javascript(stack, make_client):
    ana = preparar_ana(make_client)
    head = cabecalho(ana, "/u/ana/retrospectiva/2025")
    assert head.titulos == ["Retrospectiva 2025 de Ana Souza · DiscPlayer"]
    assert head.metas["og:title"] == head.titulos
    assert "2 jogos zerados" in head.metas["description"][0] and len(head.metas["description"]) == 1
    assert head.metas["og:image"] == [f"{ana.base}/api/share/retrospective/ana/2025.png"]
    assert head.metas["og:url"] == [f"{ana.base}/u/ana/retrospectiva/2025"]
    assert head.metas["twitter:card"] == ["summary_large_image"]


def test_html_de_jogos_perfis_e_listas(stack, make_client):
    ana = preparar_ana(make_client)
    publica = api(ana, "POST", "/api/lists", {"title": "Favoritos da Ana", "description": "Para sempre."})["list"]
    privada = api(ana, "POST", "/api/lists", {"title": "SEGREDO-DA-ANA", "is_public": False})["list"]

    jogo = cabecalho(ana, f"/jogos/{HADES}-hades")
    assert jogo.titulos == ["Hades · DiscPlayer"] and jogo.metas["og:image"][0].startswith("https://")
    perfil = cabecalho(ana, "/u/ana")
    assert perfil.titulos == ["Ana Souza (@ana) · DiscPlayer"]
    assert perfil.metas["og:image"] == [f"{ana.base}/api/share/profile/ana.png"]
    lista = cabecalho(ana, f"/listas/{publica['id']}")
    assert lista.titulos == ["Favoritos da Ana · lista de Ana Souza · DiscPlayer"]

    # Lista privada: o robô (e até a dona, pelo mesmo endereço) só vê a prévia padrão.
    resposta = ana.context.request.get(f"{ana.base}/listas/{privada['id']}")
    assert "SEGREDO-DA-ANA" not in resposta.text()
    assert Cabecalho(resposta.text()).titulos == ["DiscPlayer"]


def test_a_pagina_continua_funcionando_com_a_previa_injetada(stack, make_client):
    ana = preparar_ana(make_client)
    ana.open("/u/ana")
    expect(ana.page.get_by_role("heading", level=1)).to_have_text("Ana Souza")
    assert ana.errors == []
    ana.open("/jogos")
    expect(ana.page.locator(".game-card").first).to_be_visible()


# ------------------------------------------------------------------- celular
def test_retrospectiva_cabe_na_tela_do_celular(stack, make_client):
    ana = preparar_ana(make_client)
    movel = make_client(width=375, height=800, mobile=True)
    movel.open("/u/ana/retrospectiva/2025")
    expect(movel.page.locator(".retro-big-number")).to_be_visible()
    assert movel.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert movel.errors == []
