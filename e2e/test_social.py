"""Duas pessoas: seguir, curtir review, feed."""
from playwright.sync_api import expect

from helpers import open_game, register, set_rating


def test_seguir_curtir_e_feed(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    open_game(ana, "minecraft")
    set_rating(ana, 7)
    ana.page.get_by_label("O que você achou? (opcional)").fill("Minha review.")
    ana.page.get_by_role("button", name="Publicar").click()
    ana.page.wait_for_selector(".review-own")

    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    page = bruno.page

    # Bruno não vê botão de seguir no próprio perfil.
    bruno.open("/u/bruno")
    page.wait_for_selector(".profile-name")
    assert page.get_by_role("button", name="Seguir").count() == 0

    # Curte a review da Ana na página do jogo.
    open_game(bruno, "minecraft")
    page.wait_for_selector(".review-list .review")
    like = page.locator(".review-list .review", has_text="Ana Souza").locator(".like-btn")
    like.click()
    expect(like).to_have_attribute("aria-pressed", "true")
    like.click()  # descurtir também funciona (não existe curtida duplicada)
    expect(like).to_have_attribute("aria-pressed", "false")

    # Segue a Ana; o feed "Quem eu sigo" mostra a atividade dela.
    bruno.open("/u/ana")
    page.wait_for_selector(".profile-name")
    page.get_by_role("button", name="Seguir").click()
    page.wait_for_selector("button:has-text('Seguindo')")
    bruno.open("/")
    page.get_by_role("tab", name="Quem eu sigo").click()
    page.wait_for_selector(".activity")
    assert "Ana Souza" in page.locator("main").inner_text()

    # A Ana vê o Bruno entre os seguidores.
    ana.open("/u/ana?aba=seguidores")
    ana.page.wait_for_selector(".person")
    assert "Bruno Lima" in ana.page.locator("main").inner_text()

    assert ana.errors == [] and bruno.errors == []
