"""\"Quem você segue jogou\": na página do jogo, o que as pessoas seguidas fizeram com aquele jogo."""
import re

from playwright.sync_api import expect

from helpers import api, open_game, register
from tests.fake_rawg import by_name


def gid(nome):
    return by_name(nome)["id"]


def preparar_amigos(make_client):
    """Ana segue Bia (zerou e avaliou), Caio (jogando) e Duda (só quer jogar). Evandro jogou, mas ela não o segue."""
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    pessoas = {}
    for nome, usuario in (("Bia Lima", "bia"), ("Caio Dias", "caio"), ("Duda Reis", "duda"), ("Evandro Paz", "evandro")):
        cliente = make_client()
        register(cliente, nome, usuario)
        pessoas[usuario] = cliente
    hades = gid("Hades")
    api(pessoas["bia"], "PUT", f"/api/library/{hades}", {"status": "zerado", "is_favorite": True})
    api(pessoas["bia"], "POST", f"/api/games/{hades}/reviews", {"rating": 9.5, "body": "Uma obra-prima."})
    api(pessoas["caio"], "PUT", f"/api/library/{hades}", {"status": "jogando"})
    api(pessoas["duda"], "PUT", f"/api/library/{hades}", {"status": "quero_jogar"})
    api(pessoas["evandro"], "PUT", f"/api/library/{hades}", {"status": "zerado"})
    for usuario in ("bia", "caio", "duda"):
        api(ana, "PUT", f"/api/users/{usuario}/follow")
    return ana


def test_a_pagina_do_jogo_mostra_quem_a_pessoa_segue_e_ja_jogou(stack, make_client):
    ana = preparar_amigos(make_client)
    open_game(ana, "hades")
    bloco = ana.page.locator(".following-card")
    expect(bloco).to_be_visible()
    expect(bloco.get_by_role("heading", name="Quem você segue jogou")).to_be_visible()

    itens = bloco.locator(".following-item")
    expect(itens).to_have_count(2)  # a Duda só quer jogar e o Evandro não é seguido
    bia = itens.filter(has_text="Bia Lima")
    expect(bia).to_contain_text("Zerado")
    expect(bia.locator(".following-rating strong")).to_have_text("9,5")
    expect(bia.get_by_label("Nota 9,5 de 10")).to_be_visible()
    expect(bia).to_contain_text("favorito")
    caio = itens.filter(has_text="Caio Dias")
    expect(caio).to_contain_text("Jogando")
    expect(caio.locator(".following-rating")).to_have_count(0)  # quem não deu nota fica sem linha de nota
    expect(bloco).not_to_contain_text("Evandro")
    expect(bloco).not_to_contain_text("Duda")
    expect(bloco.locator(".following-more")).to_have_text("1 pessoa quer jogar")
    expect(bloco).not_to_contain_text("Uma obra-prima")  # o texto da review fica nas reviews, não aqui

    bloco.get_by_role("link", name="Bia Lima").click()
    expect(ana.page).to_have_url(re.compile(r"/u/bia$"))
    assert ana.errors == []


def test_a_media_entre_quem_se_segue_aparece_com_duas_notas(stack, make_client):
    ana = preparar_amigos(make_client)
    caio = make_client()
    caio.open("/entrar")
    caio.page.get_by_label("E-mail ou usuário").fill("caio")
    caio.page.get_by_label("Senha").fill("segredo-longo-123")
    caio.page.get_by_role("button", name="Entrar").last.click()
    caio.page.wait_for_selector(".user-menu-button")
    api(caio, "PUT", f"/api/library/{gid('Hades')}", {"status": "zerado"})
    api(caio, "POST", f"/api/games/{gid('Hades')}/reviews", {"rating": 8})
    open_game(ana, "hades")
    expect(ana.page.locator(".following-summary")).to_contain_text("Média entre quem você segue: 8,75 (2 notas)")


def test_sem_ninguem_seguido_que_tenha_jogado_o_bloco_nao_aparece(stack, make_client):
    ana = preparar_amigos(make_client)
    open_game(ana, "celeste")  # ninguém registrou o Celeste
    ana.page.wait_for_selector(".score-card")
    ana.page.wait_for_timeout(400)
    expect(ana.page.locator(".following-card")).to_have_count(0)
    # deixar de seguir também tira as pessoas do bloco
    api(ana, "DELETE", "/api/users/bia/follow")
    api(ana, "DELETE", "/api/users/caio/follow")
    open_game(ana, "hades")
    ana.page.wait_for_selector(".score-card")
    ana.page.wait_for_timeout(400)
    expect(ana.page.locator(".following-card")).to_have_count(0)


def test_visitante_nao_ve_o_bloco_nem_chama_a_consulta(stack, make_client):
    preparar_amigos(make_client)
    visitante = make_client()
    chamadas = []
    visitante.page.on("request", lambda req: chamadas.append(req.url) if "/following" in req.url and "/games/" in req.url else None)
    open_game(visitante, "hades")
    visitante.page.wait_for_selector(".score-card")
    visitante.page.wait_for_timeout(400)
    expect(visitante.page.locator(".following-card")).to_have_count(0)
    assert chamadas == []


def test_no_celular_o_bloco_cabe_na_tela(stack, make_client):
    preparar_amigos(make_client)
    celular = make_client(width=390, height=800, mobile=True)
    celular.open("/entrar")
    celular.page.get_by_label("E-mail ou usuário").fill("ana")
    celular.page.get_by_label("Senha").fill("segredo-longo-123")
    celular.page.get_by_role("button", name="Entrar").last.click()
    celular.page.wait_for_selector(".user-menu-button")
    open_game(celular, "hades")
    expect(celular.page.locator(".following-card")).to_be_visible()
    assert celular.page.evaluate("document.documentElement.scrollWidth") <= 391
    caixa = celular.page.locator(".following-card").bounding_box()
    assert caixa["x"] >= 0 and caixa["x"] + caixa["width"] <= 391
    assert celular.errors == []
