"""Se a RAWG cair, o site continua útil e explica o que houve."""
from helpers import open_game, register


def test_site_continua_util_sem_rawg(stack, make_client):
    c = make_client()
    page = c.page
    register(c, "Ana Souza", "ana")
    open_game(c, "minecraft")
    jogo_url = page.url
    page.get_by_role("button", name="Jogando").click()  # guarda uma cópia local do jogo
    page.wait_for_selector(".toast")

    stack.rawg_down()

    # Catálogo: erro claro, com botão para tentar de novo.
    c.open("/jogos?q=zelda")
    page.wait_for_selector(".state-error")
    assert "Tentar de novo" in page.locator(".state-error").inner_text()

    # Home: as listas de jogos falham sozinhas; o restante da página continua.
    c.open("/")
    page.wait_for_selector(".state-error")
    assert page.locator("h1").count() == 1

    # Jogo já conhecido abre com a cópia local e um aviso de dados parciais.
    page.goto(jogo_url, wait_until="networkidle")
    page.wait_for_selector(".game-title")
    assert page.locator(".notice").count() == 1

    # Busca do cabeçalho: jogadores e listas seguem funcionando, e o aviso diz o que faltou.
    page.get_by_role("combobox", name="Pesquisar jogos").fill("ana")
    page.wait_for_selector(".search-option")
    assert page.locator(".search-group", has_text="Jogadores").count() == 1
    assert "indisponível" in page.locator(".search-status").inner_text()

    # A RAWG volta e o botão recupera a tela sem recarregar a página.
    c.open("/jogos?q=zelda")
    page.wait_for_selector(".state-error")
    stack.rawg_up()
    page.get_by_role("button", name="Tentar de novo").click()
    page.wait_for_selector(".game-card")
