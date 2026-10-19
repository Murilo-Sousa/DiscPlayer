"""Guardas de rota, privacidade, validação no servidor, teclado e celular."""
import re

from helpers import PASSWORD, login, open_game, register


def test_rota_protegida_volta_para_onde_a_pessoa_queria(stack, make_client):
    dona = make_client()
    register(dona, "Ana Souza", "ana")
    dona.page.get_by_role("button", name="Menu de Ana Souza").click()
    dona.page.get_by_role("button", name="Sair").click()
    dona.page.wait_for_selector("a:has-text('Entrar')")

    dona.open("/diario")
    dona.page.wait_for_url(re.compile(r"/entrar\?proximo=%2Fdiario"))
    dona.page.get_by_label("E-mail ou usuário").fill("ana")
    dona.page.get_by_label("Senha").fill("senha-errada-123")
    dona.page.get_by_role("button", name="Entrar").last.click()
    dona.page.wait_for_selector(".form-error")
    assert "incorretos" in dona.page.locator(".form-error").inner_text()
    login(dona, "ana")
    dona.page.wait_for_url(re.compile(r"/diario$"))


def test_proximo_malicioso_e_ignorado(stack, make_client):
    c = make_client()
    register(c, "Ana Souza", "ana")
    c.page.get_by_role("button", name="Menu de Ana Souza").click()
    c.page.get_by_role("button", name="Sair").click()
    c.page.wait_for_selector("a:has-text('Entrar')")
    c.open("/entrar?proximo=//evil.example")
    login(c, "ana")
    c.page.wait_for_selector(".user-menu-button")
    assert c.page.url == stack.url + "/"


def test_lista_privada_so_aparece_para_a_dona(stack, make_client):
    dona = make_client()
    register(dona, "Ana Souza", "ana")
    open_game(dona, "hades")
    dona.page.get_by_role("button", name="Guardar em lista").click()
    dona.page.wait_for_selector("dialog[open]")
    dona.page.get_by_label("Nova lista com este jogo").fill("Segredo")
    dona.page.get_by_role("button", name="Criar lista").click()
    dona.page.wait_for_selector(".check-row")
    dona.page.get_by_role("button", name="Concluir").click()

    dona.open("/listas?aba=minhas")
    dona.page.locator(".list-card-link").first.click()
    dona.page.wait_for_selector(".list-items")
    list_url = dona.page.url
    dona.page.get_by_role("button", name="Editar").click()
    dona.page.wait_for_selector("dialog[open]")
    dona.page.get_by_label("Privada: só você vê").check()
    dona.page.get_by_role("button", name="Salvar", exact=True).click()
    dona.page.wait_for_selector(".badge:has-text('Privada')")

    visitante = make_client()
    visitante.page.goto(list_url, wait_until="networkidle")
    visitante.page.wait_for_selector("h1")
    assert "não encontrada" in visitante.page.locator("h1").inner_text().lower()
    visitante.open("/listas")
    visitante.page.wait_for_selector("h1")
    assert "Segredo" not in visitante.page.locator("main").inner_text()


def test_servidor_rejeita_nota_fora_do_passo(stack, make_client):
    c = make_client()
    register(c, "Ana Souza", "ana")
    open_game(c, "hades")
    jogo_id = re.search(r"/jogos/(\d+)", c.page.url).group(1)
    status, campos = c.page.evaluate(
        """async (id) => {
          const me = await (await fetch('/api/auth/me')).json();
          const r = await fetch(`/api/games/${id}/reviews`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
            body: JSON.stringify({rating: 7.3}),
          });
          return [r.status, (await r.json()).error.fields];
        }""",
        jogo_id,
    )
    assert status == 422 and "rating" in campos


def test_servidor_exige_csrf(stack, make_client):
    c = make_client()
    register(c, "Ana Souza", "ana")
    open_game(c, "hades")
    jogo_id = re.search(r"/jogos/(\d+)", c.page.url).group(1)
    status, codigo = c.page.evaluate(
        """async (id) => {
          const r = await fetch(`/api/games/${id}/reviews`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({rating: 7}),
          });
          return [r.status, (await r.json()).error.code];
        }""",
        jogo_id,
    )
    assert (status, codigo) == (403, "csrf_invalid")


def test_busca_do_cabecalho_por_teclado(stack, client):
    page = client.page
    client.open("/")
    box = page.get_by_role("combobox", name="Pesquisar jogos")
    box.fill("hades")
    page.wait_for_selector(".search-option")
    page.keyboard.press("ArrowDown")
    selecionada = page.locator(".search-option[aria-selected=true]")
    assert selecionada.count() == 1
    assert box.get_attribute("aria-activedescendant") == selecionada.get_attribute("id")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/jogos/\d+"))


def test_paginas_inexistentes_explicam_o_que_houve(stack, client):
    page = client.page
    for path in ("/jogos/abc", "/jogos/999999999", "/u/ninguem", "/listas/999999", "/rota/que/nao/existe"):
        client.open(path)
        page.wait_for_selector("h1")
        titulo = page.locator("h1").inner_text().lower()
        assert "não encontrad" in titulo, f"{path} -> {titulo!r}"


def test_celular_sem_rolagem_horizontal(stack, make_client):
    c = make_client(width=375, height=800, mobile=True)
    register(c, "Ana Souza", "ana")
    for path in ("/", "/jogos", "/diario", "/u/ana", "/listas", "/configuracoes"):
        c.open(path)
        c.page.wait_for_timeout(300)
        sobra = c.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert sobra <= 0, f"{path} rola na horizontal em 375px (sobra {sobra}px)"
