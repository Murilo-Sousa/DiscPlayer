"""Regras do diário vistas no navegador: cada status só mostra e permite o que faz sentido.

"Quero jogar" é um jogo que ainda não foi começado: sem datas, sem favorito, sem nota. Só um jogo zerado tem data
de término. Jogo que ainda não saiu só vai para a fila. Tirar o jogo do diário leva a nota junto.
"""
import re
from datetime import date

from playwright.sync_api import expect

from helpers import api, marcar_status, open_game, register, set_rating
from tests.fake_rawg import by_name


def gid(nome):
    return by_name(nome)["id"]


def diario(client):
    return client.page.locator("section[aria-labelledby=diary-title]")


def nota(client):
    return client.page.locator("section[aria-labelledby=review-title]")


def test_cada_status_mostra_so_o_que_faz_sentido(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    painel = diario(client)

    # Fora do diário: o painel só pergunta o status; a nota fica trancada com a explicação.
    expect(painel.get_by_label("Comecei em")).to_have_count(0)
    expect(nota(client)).to_contain_text("Registre o jogo no seu diário")
    expect(nota(client).locator("input[type=range]")).to_have_count(0)

    # Na fila: sem datas, sem favorito, sem nota.
    marcar_status(client, "Quero jogar")
    expect(painel.get_by_label("Comecei em")).to_have_count(0)
    expect(painel.get_by_label("Terminei em")).to_have_count(0)
    expect(painel.get_by_role("button", name="Favoritar")).to_have_count(0)
    expect(painel.get_by_role("button", name="Jogar de novo")).to_have_count(0)
    expect(painel).to_contain_text("Na fila")
    expect(nota(client)).to_contain_text("Você marcou este jogo como “Quero jogar”")
    expect(nota(client).locator("input[type=range]")).to_have_count(0)

    # Jogando: data de início (já preenchida com hoje), favorito e nota; nada de data de término.
    marcar_status(client, "Jogando")
    inicio = painel.get_by_label("Comecei em")
    expect(inicio).to_have_value(re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    expect(painel.get_by_label("Terminei em")).to_have_count(0)
    expect(painel.get_by_role("button", name="Favoritar")).to_be_visible()
    expect(nota(client).locator("input[type=range]")).to_have_count(1)

    # Zerado: aparece a data de término, preenchida.
    marcar_status(client, "Zerado")
    expect(painel.get_by_label("Terminei em")).to_have_value(re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    expect(painel.get_by_role("button", name="Jogar de novo")).to_be_visible()

    # Pausado: a data de término some (e é limpa no servidor); "jogar de novo" não se aplica, retoma-se em "Jogando".
    marcar_status(client, "Pausado")
    expect(painel.get_by_label("Terminei em")).to_have_count(0)
    expect(painel.get_by_label("Comecei em")).to_have_value(re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    expect(painel.get_by_role("button", name="Jogar de novo")).to_have_count(0)
    marcar_status(client, "Zerado")
    expect(painel.get_by_label("Terminei em")).to_have_value(date.today().isoformat())  # a data velha não voltou

    # Abandonado: dá para jogar de novo, mas não há data de término.
    marcar_status(client, "Abandonado")
    expect(painel.get_by_label("Terminei em")).to_have_count(0)
    expect(painel.get_by_role("button", name="Jogar de novo")).to_be_visible()
    assert client.errors == []


def test_voltar_para_a_fila_limpa_datas_e_favorito(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    marcar_status(client, "Jogando")
    diario(client).get_by_role("button", name="Favoritar").click()
    expect(diario(client).get_by_role("button", name="Favorito")).to_be_visible()
    marcar_status(client, "Quero jogar")
    expect(diario(client).get_by_role("button", name="Favorito")).to_have_count(0)
    expect(diario(client).get_by_label("Comecei em")).to_have_count(0)
    client.page.reload()
    client.page.wait_for_selector(".game-title")
    expect(diario(client)).to_contain_text("Na fila")
    entrada = api(client, "GET", "/api/library")["items"][0]["entry"]
    assert (entrada["started_at"], entrada["completed_at"], entrada["is_favorite"]) == (None, None, False)


def test_com_nota_o_jogo_nao_volta_para_a_fila_e_a_tela_explica_por_que(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    marcar_status(client, "Zerado")
    set_rating(client, 9)
    client.page.get_by_role("button", name="Publicar").click()
    client.page.wait_for_selector(".review-own")
    fila = diario(client).locator(".status-picker").get_by_role("button", name="Quero jogar", exact=True)
    expect(fila).to_be_disabled()
    expect(diario(client)).to_contain_text("Você já avaliou este jogo, então ele não volta para a fila")
    # Os outros status continuam livres.
    marcar_status(client, "Pausado")


def test_tirar_do_diario_leva_a_nota_junto_e_avisa(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    marcar_status(client, "Zerado")
    set_rating(client, 9)
    client.page.get_by_role("button", name="Publicar").click()
    client.page.wait_for_selector(".review-own")
    expect(client.page.locator(".score-main")).to_be_visible()  # a média da comunidade tem a nota dela

    diario(client).get_by_role("button", name="Remover do diário").click()
    dialogo = client.page.locator("dialog[open]")
    expect(dialogo).to_contain_text("A sua nota e a sua review também saem do DiscPlayer")
    dialogo.get_by_role("button", name="Remover").click()
    # Espera o aviso certo: os de antes ("Review publicada.") ainda estão na tela.
    expect(client.page.locator(".toast", has_text="Jogo e nota removidos do seu diário")).to_be_visible()
    expect(nota(client)).to_contain_text("Registre o jogo no seu diário")
    expect(client.page.locator(".review-own")).to_have_count(0)
    expect(client.page.locator(".score-main")).to_have_count(0)  # sem notas na comunidade
    expect(client.page.locator(".game-score")).to_contain_text("Ainda sem notas")


def test_tela_desatualizada_nao_apaga_uma_nota_que_ela_nao_mostrava(stack, client):
    """A nota foi dada em outra aba: remover o jogo aqui não pode levá-la embora sem o aviso ter sido visto."""
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    marcar_status(client, "Zerado")
    api(client, "POST", f"/api/games/{gid('Minecraft')}/reviews", {"rating": 8})  # "em outra aba"

    diario(client).get_by_role("button", name="Remover do diário").click()
    dialogo = client.page.locator("dialog[open]")
    expect(dialogo).not_to_contain_text("sua nota")  # esta tela ainda não sabe da nota
    dialogo.get_by_role("button", name="Remover").click()
    expect(client.page.locator(".toast", has_text="nada foi removido")).to_be_visible()
    assert len(api(client, "GET", "/api/library")["items"]) == 1  # o jogo continua no diário
    # a tela se atualizou: agora a nota aparece e o aviso do diálogo fala dela
    expect(client.page.locator(".review-own")).to_be_visible()
    diario(client).get_by_role("button", name="Remover do diário").click()
    expect(client.page.locator("dialog[open]")).to_contain_text("A sua nota e a sua review também saem do DiscPlayer")


def test_tirar_do_diario_sem_nota_nao_fala_de_nota(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    marcar_status(client, "Jogando")
    diario(client).get_by_role("button", name="Remover do diário").click()
    dialogo = client.page.locator("dialog[open]")
    expect(dialogo).not_to_contain_text("sua nota")
    dialogo.get_by_role("button", name="Remover").click()
    aviso = client.page.locator(".toast", has_text="Jogo removido do seu diário.")
    expect(aviso).to_be_visible()
    expect(aviso).not_to_contain_text("nota")


def test_jogo_nao_lancado_so_vai_para_a_fila(stack, client):
    register(client, "Ana Souza", "ana")
    open_game(client, "farol")
    painel = diario(client)
    expect(painel).to_contain_text("Lança em")
    botoes = painel.locator(".status-picker button")
    expect(botoes).to_have_count(5)
    for nome in ("Jogando", "Pausado", "Zerado", "Abandonado"):
        expect(painel.locator(".status-picker").get_by_role("button", name=nome, exact=True)).to_be_disabled()
    fila = painel.locator(".status-picker").get_by_role("button", name="Quero jogar", exact=True)
    expect(fila).to_be_enabled()
    marcar_status(client, "Quero jogar")
    expect(nota(client)).to_contain_text("só será lançado em")
    expect(nota(client).locator("input[type=range]")).to_have_count(0)


def test_servidor_recusa_o_que_a_tela_nem_oferece(stack, client):
    """Quem fala direto com a API recebe o motivo, e nada é salvo."""
    register(client, "Ana Souza", "ana")
    token = client.context.request.get(f"{client.base}/api/auth/me").json()["csrf_token"]

    def enviar(metodo, caminho, corpo):
        return client.context.request.fetch(
            f"{client.base}{caminho}", method=metodo, data=corpo, headers={"X-CSRF-Token": token}
        )

    hades = gid("Hades")
    assert enviar("PUT", f"/api/library/{hades}", {"status": "quero_jogar", "started_at": "2025-01-10"}).status == 422
    assert enviar("PUT", f"/api/library/{hades}", {"status": "quero_jogar", "is_favorite": True}).status == 409
    avaliar = enviar("POST", f"/api/games/{hades}/reviews", {"rating": 8})
    assert avaliar.status == 409 and avaliar.json()["error"]["code"] == "not_played"
    assert enviar("PUT", f"/api/library/{gid('Farol do Amanhã')}", {"status": "zerado"}).status == 409
    assert api(client, "GET", "/api/library")["items"] == []

    # Tirar do diário um jogo com nota exige a confirmação; sem ela, nada é apagado.
    assert enviar("PUT", f"/api/library/{hades}", {"status": "zerado"}).status == 201
    assert enviar("POST", f"/api/games/{hades}/reviews", {"rating": 8}).status == 201
    sem_aviso = enviar("DELETE", f"/api/library/{hades}", None)
    assert sem_aviso.status == 409 and sem_aviso.json()["error"]["code"] == "review_would_be_removed"
    assert len(api(client, "GET", "/api/library")["items"]) == 1
    assert enviar("DELETE", f"/api/library/{hades}", {"with_review": True}).status == 200
    assert api(client, "GET", "/api/library")["items"] == []


def test_ninguem_ve_o_botao_de_curtir_na_propria_review(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    open_game(ana, "minecraft")
    marcar_status(ana, "Zerado")
    set_rating(ana, 7)
    ana.page.get_by_label("O que você achou? (opcional)").fill("Gostei muito.")
    ana.page.get_by_role("button", name="Publicar").click()
    ana.page.wait_for_selector(".review-own")
    ana.page.reload()
    ana.page.wait_for_selector(".review-list .review")
    propria = ana.page.locator(".review-list .review", has_text="Gostei muito.")
    expect(propria.locator(".like-btn")).to_have_count(0)

    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    open_game(bruno, "minecraft")
    bruno.page.wait_for_selector(".review-list .review")
    expect(bruno.page.locator(".review-list .review", has_text="Gostei muito.").locator(".like-btn")).to_have_count(1)
    assert ana.errors == [] and bruno.errors == []


def test_na_aba_da_fila_nao_ha_favoritos_nem_ordenar_por_nota(stack, client):
    register(client, "Ana Souza", "ana")
    api(client, "PUT", f"/api/library/{gid('Super Metroid')}", {"status": "quero_jogar"})
    api(client, "PUT", f"/api/library/{gid('Hades')}", {"status": "zerado", "completed_at": "2025-03-20"})
    client.open("/diario")
    client.page.wait_for_selector(".game-card")
    ordenar = client.page.get_by_label("Ordenar")
    expect(client.page.get_by_label("Só favoritos", exact=False)).to_be_visible()
    expect(ordenar.locator("option")).to_have_count(4)

    client.page.get_by_role("tab", name=re.compile("Quero jogar")).click()
    expect(client.page.locator(".game-card")).to_have_count(1)
    expect(client.page.get_by_label("Só favoritos", exact=False)).to_have_count(0)
    expect(ordenar.locator("option")).to_have_count(2)  # sem "Maior nota" nem "Data de término"

    client.page.get_by_role("tab", name=re.compile("Pausado")).click()
    expect(ordenar.locator("option")).to_have_count(3)  # tem nota, mas não tem data de término
    client.page.get_by_role("tab", name=re.compile("Zerado")).click()
    expect(ordenar.locator("option")).to_have_count(4)


def test_no_celular_o_painel_do_diario_cabe_na_tela_em_cada_status(stack, make_client):
    c = make_client(width=390, height=800, mobile=True)
    register(c, "Ana Souza", "ana")
    open_game(c, "minecraft")
    for nome in ("Quero jogar", "Jogando", "Zerado", "Abandonado"):
        marcar_status(c, nome)
        largura = c.page.evaluate("document.documentElement.scrollWidth")
        assert largura <= 391, f"{nome}: rolagem horizontal ({largura}px)"
    assert c.errors == []
