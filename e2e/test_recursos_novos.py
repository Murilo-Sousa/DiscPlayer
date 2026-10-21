"""Spoilers, jogar de novo, foto enviada e exclusão de conta, pela interface."""
import io
import re

from PIL import Image
from playwright.sync_api import expect

from helpers import PASSWORD, login, open_game, register, set_rating, toast_text

SEGREDO = "No final o mentor era o vilão desde o começo."


def foto(cor=(200, 60, 60), tamanho=(640, 480), formato="PNG") -> bytes:
    imagem = Image.new("RGB", tamanho, cor)
    saida = io.BytesIO()
    imagem.save(saida, formato)
    return saida.getvalue()


def escolher_arquivo(page, conteudo: bytes, nome: str, tipo: str) -> None:
    page.get_by_test_id("photo-input").set_input_files(files=[{"name": nome, "mimeType": tipo, "buffer": conteudo}])


def imagem_carregou(locator) -> bool:
    return locator.evaluate("img => img.complete && img.naturalWidth > 0")


# ------------------------------------------------------------------- spoilers
def test_review_com_spoiler_fica_escondida_ate_o_clique(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    titulo = open_game(ana, "minecraft")
    set_rating(ana, 9)
    texto = ana.page.get_by_label("O que você achou? (opcional)")
    caixa = ana.page.get_by_label("Esta review contém spoilers")
    expect(caixa).to_be_disabled()  # sem texto não há o que esconder
    texto.fill(SEGREDO)
    expect(caixa).to_be_enabled()
    caixa.check()
    ana.page.get_by_role("button", name="Publicar").click()
    ana.page.wait_for_selector(".review-own")
    # A autora vê o que escreveu, com o selo de que está marcada.
    assert SEGREDO in ana.page.locator(".review-own").inner_text()
    assert "Contém spoilers" in ana.page.locator(".review-own").inner_text()

    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    page = bruno.page
    open_game(bruno, "minecraft")
    cartao = page.locator(".review-list .review", has_text="Ana Souza")
    cartao.wait_for()
    assert "Contém spoilers" in cartao.inner_text()
    assert SEGREDO not in page.content()  # o texto nem está na página
    assert SEGREDO not in cartao.inner_text()

    cartao.get_by_role("button", name="Mostrar texto").click()
    expect(cartao.locator(".review-body")).to_contain_text(SEGREDO)
    expect(cartao.locator(".review-body")).to_be_focused()  # o foco acompanha o texto revelado
    cartao.get_by_role("button", name="Esconder o texto de novo").click()
    expect(cartao.locator(".review-body")).to_have_count(0)
    assert SEGREDO not in page.content()

    # Perfil da Ana e atividade: aviso em vez do trecho.
    bruno.open("/u/ana")
    page.wait_for_selector(".profile-name")
    page.get_by_role("tab", name=re.compile("Atividade|Reviews")).first.click()
    assert SEGREDO not in page.content()

    bruno.open("/")
    page.wait_for_selector(".activity, .review")
    assert SEGREDO not in page.content() or "Mostrar texto" in page.content()
    bruno.open(f"/busca?q=mentor")
    page.wait_for_selector("main")
    assert SEGREDO not in page.content()
    assert ana.errors == [] and bruno.errors == []


def test_ana_pode_editar_e_tirar_o_aviso(stack, client):
    page = client.page
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    set_rating(client, 5)
    page.get_by_label("O que você achou? (opcional)").fill(SEGREDO)
    page.get_by_label("Esta review contém spoilers").check()
    page.get_by_role("button", name="Publicar").click()
    page.wait_for_selector(".review-own")
    page.get_by_role("button", name="Editar").click()
    expect(page.get_by_label("Esta review contém spoilers")).to_be_checked()
    page.get_by_label("Esta review contém spoilers").uncheck()
    page.get_by_role("button", name="Salvar alterações").click()
    page.wait_for_selector(".review-own")
    assert "Contém spoilers" not in page.locator(".review-own").inner_text()
    assert client.errors == []


# ------------------------------------------------------------- jogar de novo
def test_jogar_de_novo_guarda_a_jogada_e_comeca_outra(stack, client):
    page = client.page
    register(client, "Ana Souza", "ana")
    open_game(client, "minecraft")
    assert page.get_by_role("button", name="Jogar de novo").count() == 0  # ainda não jogou

    page.get_by_role("button", name="Zerado").click()
    page.wait_for_selector(".toast")
    expect(page.get_by_role("button", name="Jogar de novo")).to_be_visible()
    assert page.locator(".playthroughs").count() == 0  # o histórico só aparece depois do primeiro recomeço

    page.get_by_role("button", name="Jogar de novo").click()
    dialogo = page.locator("dialog[open]")
    expect(dialogo).to_contain_text("fica guardada no histórico")
    dialogo.get_by_role("button", name="Cancelar").click()
    assert page.locator(".playthroughs").count() == 0

    page.get_by_role("button", name="Jogar de novo").click()
    page.locator("dialog[open]").get_by_role("button", name="Jogar de novo").click()
    assert "Nova jogada" in toast_text(client)

    expect(page.get_by_role("button", name="Jogando")).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_role("button", name="Jogar de novo")).to_have_count(0)  # jogando: não se recomeça
    linhas = page.locator(".playthrough")
    expect(linhas).to_have_count(2)
    expect(linhas.nth(0)).to_contain_text("Jogada 1")
    expect(linhas.nth(0)).to_contain_text("Zerado")
    expect(linhas.nth(1)).to_contain_text("Jogada 2")
    expect(linhas.nth(1)).to_contain_text("atual")

    # Recarregar mantém o histórico (vem do servidor).
    page.reload(wait_until="networkidle")
    expect(page.locator(".playthrough")).to_have_count(2)

    # O diário mostra a contagem de jogadas.
    client.open("/diario")
    page.wait_for_selector(".game-card")
    assert "2ª jogada" in page.locator("main").inner_text()

    # Excluir a jogada antiga.
    open_game(client, "minecraft")
    page.get_by_role("button", name="Excluir a jogada 1").click()
    dialogo = page.locator("dialog[open]")
    expect(dialogo).to_contain_text("Excluir a jogada 1?")
    dialogo.get_by_role("button", name="Excluir jogada").click()
    expect(page.locator(".playthroughs")).to_have_count(0)
    assert client.errors == []


def test_recomecar_aparece_no_feed_como_voltou_a_jogar(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    open_game(ana, "minecraft")
    ana.page.get_by_role("button", name="Abandonado").click()
    ana.page.wait_for_selector(".toast")
    ana.page.get_by_role("button", name="Jogar de novo").click()
    ana.page.locator("dialog[open]").get_by_role("button", name="Jogar de novo").click()
    expect(ana.page.locator(".playthrough")).to_have_count(2)

    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    bruno.open("/u/ana")
    bruno.page.wait_for_selector(".profile-name")
    bruno.page.get_by_role("tab", name="Atividade").click()
    bruno.page.wait_for_selector(".activity")
    texto = bruno.page.locator("main").inner_text().lower()  # no perfil a frase começa com maiúscula
    assert "voltou a jogar minecraft" in texto and "abandonou minecraft" in texto
    assert ana.errors == [] and bruno.errors == []


# ------------------------------------------------------------ foto enviada
def test_envio_de_foto_com_previa_troca_e_remocao(stack, make_client):
    ana = make_client()
    page = ana.page
    register(ana, "Ana Souza", "ana")
    ana.open("/configuracoes")
    page.wait_for_selector(".settings-photo")
    assert page.locator(".settings-photo img").count() == 0  # sem foto: iniciais
    assert page.get_by_role("button", name="Remover foto").count() == 0

    # Arquivos que não são JPG/PNG/WebP são recusados já no navegador.
    escolher_arquivo(page, b"texto qualquer", "nota.txt", "text/plain")
    expect(page.get_by_role("alert")).to_contain_text("JPG, PNG ou WebP")
    assert page.get_by_role("button", name="Salvar foto").count() == 0

    # Um "PNG" falso passa pelo navegador e é barrado pelo servidor, com a mensagem dele.
    escolher_arquivo(page, b"isto nao e uma imagem de verdade", "falsa.png", "image/png")
    page.get_by_role("button", name="Salvar foto").click()
    expect(page.get_by_role("alert")).to_contain_text("Não foi possível ler este arquivo")
    page.get_by_role("button", name="Cancelar").click()

    # Foto de verdade: prévia (blob:, liberado na política de segurança), salvar, aparecer.
    escolher_arquivo(page, foto(), "minha-foto.png", "image/png")
    previa = page.get_by_test_id("photo-preview").locator("img")
    expect(previa).to_be_visible()
    assert previa.get_attribute("src").startswith("blob:")
    assert imagem_carregou(previa)
    page.get_by_role("button", name="Salvar foto").click()
    assert "Foto atualizada" in toast_text(ana)
    imagem = page.locator(".settings-photo .avatar img")
    expect(imagem).to_have_attribute("src", re.compile(r"^/api/avatars/"))
    assert imagem_carregou(imagem)

    # Outra pessoa vê a foto no perfil (arquivo servido pelo próprio site).
    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    bruno.open("/u/ana")
    bruno.page.wait_for_selector(".profile-name")
    perfil = bruno.page.locator(".profile-avatar img")
    expect(perfil).to_have_attribute("src", re.compile(r"^/api/avatars/"))
    assert imagem_carregou(perfil)

    # Trocar e remover.
    expect(page.get_by_role("button", name="Trocar foto")).to_be_visible()  # com foto, o botão muda de nome
    escolher_arquivo(page, foto((30, 30, 200), (300, 300), "JPEG"), "outra.jpg", "image/jpeg")
    page.get_by_role("button", name="Salvar foto").click()
    page.wait_for_selector(".toast")
    page.get_by_role("button", name="Remover foto").click()
    expect(page.get_by_role("button", name="Escolher foto")).to_be_visible()
    assert page.locator(".settings-photo .avatar img").count() == 0
    # O único "erro" do console é o 422 que provocamos de propósito com o PNG falso.
    assert ana.errors == ["console.error: Failed to load resource: the server responded with a status of 422 (UNPROCESSABLE ENTITY)"]
    assert bruno.errors == []


def test_o_campo_de_endereco_da_foto_nao_existe_mais(stack, client):
    register(client, "Ana Souza", "ana")
    client.open("/configuracoes")
    client.page.wait_for_selector(".settings-photo")
    assert client.page.locator("input[type=url]").count() == 0


# -------------------------------------------------------------- excluir conta
def test_excluir_conta_pede_a_senha_e_apaga_tudo(stack, make_client):
    ana = make_client()
    register(ana, "Ana Souza", "ana")
    open_game(ana, "minecraft")
    set_rating(ana, 7)
    ana.page.get_by_label("O que você achou? (opcional)").fill("Review da Ana.")
    ana.page.get_by_role("button", name="Publicar").click()
    ana.page.wait_for_selector(".review-own")

    bruno = make_client()
    register(bruno, "Bruno Lima", "bruno")
    open_game(bruno, "minecraft")
    like = bruno.page.locator(".review-list .review", has_text="Ana Souza").locator(".like-btn")
    like.click()
    expect(like).to_have_attribute("aria-pressed", "true")

    page = ana.page
    ana.open("/configuracoes")
    page.get_by_role("button", name="Excluir minha conta…").click()
    dialogo = page.locator("dialog[open]")
    expect(dialogo).to_contain_text("Isto apaga para sempre")

    # Sem senha e com senha errada: nada é apagado e o erro aparece junto do campo.
    dialogo.get_by_role("button", name="Excluir definitivamente").click()
    expect(dialogo.locator(".field-error")).to_contain_text("Informe a sua senha")
    dialogo.get_by_label("Digite a sua senha para confirmar").fill("senha-errada-999")
    dialogo.get_by_role("button", name="Excluir definitivamente").click()
    expect(dialogo.locator(".field-error")).to_contain_text("Senha incorreta")
    dialogo.get_by_role("button", name="Cancelar").click()
    ana.open("/u/ana")
    page.wait_for_selector(".profile-name")  # a conta continua lá

    # Com a senha certa: conta apagada, volta para a página inicial (não para o "entre para continuar").
    ana.open("/configuracoes")
    page.get_by_role("button", name="Excluir minha conta…").click()
    dialogo = page.locator("dialog[open]")
    dialogo.get_by_label("Digite a sua senha para confirmar").fill(PASSWORD)
    dialogo.get_by_role("button", name="Excluir definitivamente").click()
    page.wait_for_url(re.compile(r"/$"))
    assert "Sua conta foi excluída" in toast_text(ana)
    expect(page.get_by_role("link", name="Entrar").first).to_be_visible()  # saiu da sessão

    # Entrar com ela não funciona mais, e o nome fica livre.
    ana.open("/entrar")
    login(ana, "ana@example.com")
    expect(page.locator(".form-error")).to_be_visible()
    ana.open("/u/ana")
    expect(page.locator("main")).to_contain_text("não encontrado", ignore_case=True)

    # Para o Bruno: a review e a curtida sumiram junto, o resto dele continua.
    open_game(bruno, "minecraft")
    assert bruno.page.locator(".review-list .review", has_text="Ana Souza").count() == 0
    assert "Review da Ana." not in bruno.page.content()
    bruno.open("/u/bruno")
    bruno.page.wait_for_selector(".profile-name")
    # Só os "falhou ao carregar" esperados (senha errada = 403, conta apagada = 404/401); nenhum erro de script.
    assert [e for e in ana.errors if not e.startswith("console.error: Failed to load resource")] == []
    assert bruno.errors == []
