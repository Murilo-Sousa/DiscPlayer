"""Uma pessoa nova usa o DiscPlayer do começo ao fim."""
import re
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect

from helpers import PASSWORD, login, open_game, register, set_rating


def test_jornada_completa(stack, client):
    page = client.page

    # Visitante: a home convida, não finge atividade.
    client.open("/")
    assert "O diário" in page.locator("h1").inner_text()
    assert page.get_by_role("link", name="Criar conta").count() >= 1

    # Cadastro com campos vazios mostra os erros ao lado dos campos.
    client.open("/cadastro")
    page.get_by_role("button", name="Criar conta").last.click()
    assert page.locator(".field-error").count() >= 3

    register(client, "Ana Souza", "ana")

    # Jogo: status, nota, texto.
    titulo = open_game(client, "minecraft")
    page.get_by_role("button", name="Jogando").click()
    page.wait_for_selector(".toast")
    set_rating(client, 7)  # 5 + 7 * 0,5 = 8,5
    page.get_by_label("O que você achou? (opcional)").fill("Curto e bonito.\n\nA trilha sonora fica na cabeça.")
    page.get_by_role("button", name="Publicar").click()
    page.wait_for_selector(".review-own")
    own = page.locator(".review-own").inner_text()
    assert "8,5" in own and "trilha sonora" in own

    # Lista nova criada a partir do jogo.
    page.get_by_role("button", name="Guardar em lista").click()
    page.wait_for_selector("dialog[open]")
    page.get_by_label("Nova lista com este jogo").fill("Para rejogar")
    page.get_by_role("button", name="Criar lista").click()
    page.wait_for_selector(".check-row")
    page.get_by_role("button", name="Concluir").click()

    # Diário e perfil mostram dados reais dessa pessoa.
    client.open("/diario")
    page.wait_for_selector(".game-card")
    assert titulo in page.locator("main").inner_text()
    client.open("/u/ana")
    page.wait_for_selector(".stats-strip")
    assert "Ana Souza" in page.locator(".profile-name").inner_text()
    client.open("/listas?aba=minhas")
    assert "Para rejogar" in page.locator("main").inner_text()

    # Sair e entrar de novo (a sessão vive em cookie HttpOnly; nada sensível no localStorage).
    page.get_by_role("button", name="Menu de Ana Souza").click()
    page.get_by_role("button", name="Sair").click()
    page.wait_for_selector("a:has-text('Entrar')")
    storage = page.evaluate("JSON.stringify([localStorage, sessionStorage])")
    assert "csrf" not in storage.lower() and "senha" not in storage.lower() and PASSWORD not in storage
    assert "session" not in page.evaluate("document.cookie").lower()  # cookie é HttpOnly

    client.open("/entrar")
    login(client, "ana@example.com")
    page.wait_for_selector(".user-menu-button")

    assert client.errors == []


def test_catalogo_filtros_e_paginacao_na_url(stack, client):
    page = client.page
    client.open("/jogos?genero=action&ordem=rating")
    page.wait_for_selector(".game-card")
    assert page.locator(".game-card").count() >= 1
    # O estado dos filtros mora na URL: recarregar mantém o resultado.
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".game-card")
    assert re.search(r"genero=action", page.url)
    assert client.errors == []


def test_configuracoes_editam_perfil_e_exigem_https_na_foto(stack, client):
    page = client.page
    register(client, "Ana Souza", "ana")
    client.open("/configuracoes")
    page.wait_for_selector(".settings-form")

    page.get_by_label("Bio").fill("Jogo de tudo. Principalmente RPG.")
    page.get_by_label("Endereço da foto").fill("http://media.rawg.io/avatar.png")
    page.get_by_role("button", name="Salvar").click()
    page.wait_for_selector(".field-error")
    assert "https://" in page.locator(".field-error").inner_text()

    page.get_by_label("Endereço da foto").fill("https://media.rawg.io/avatar.png")
    page.get_by_role("button", name="Salvar").click()
    page.wait_for_selector(".toast")

    client.open("/u/ana")
    page.wait_for_selector(".profile-name")
    assert "Principalmente RPG" in page.locator("main").inner_text()
    assert page.locator("main img[src='https://media.rawg.io/avatar.png']").count() >= 1
    assert client.errors == []


def test_data_automatica_usa_o_fuso_de_quem_joga(stack, make_client):
    """Às 22h30 em São Paulo já é "amanhã" em UTC: o diário deve registrar o dia local."""
    c = make_client(timezone_id="America/Sao_Paulo")
    page = c.page
    agora = datetime.now(timezone.utc)
    # 01h30 UTC do dia de hoje = 22h30 do dia anterior em São Paulo (UTC-3).
    page.clock.set_fixed_time(datetime(agora.year, agora.month, agora.day, 1, 30, tzinfo=timezone.utc))
    dia_local = (agora.date() - timedelta(days=1)).isoformat()

    register(c, "Ana Souza", "ana")
    open_game(c, "minecraft")
    page.get_by_role("button", name="Jogando").click()
    expect(page.get_by_label("Comecei em")).to_have_value(dia_local)

    page.get_by_role("button", name="Zerado").click()
    expect(page.get_by_label("Terminei em")).to_have_value(dia_local)
    assert c.errors == []
