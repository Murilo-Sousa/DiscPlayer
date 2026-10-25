"""Imagens de compartilhamento (PNG 1200 x 630): o que aparece quando um link do site é colado em outro app.

As imagens são desenhadas no servidor só com dados públicos, ficam em cache por alguns minutos e a chave
do cache inclui os próprios dados desenhados.
"""
from __future__ import annotations

import io
import sys

import pytest
from PIL import Image

from app import create_app
from app import db as database
from app.routes import share
from app.security import reset_rate_limits
from app.services import cards

from . import images
from .conftest import CELESTE, HADES, Api

ACCENT = (229, 210, 91)  # #e5d25b


@pytest.fixture(autouse=True)
def fresh_cache():
    share._cache.clear()  # o cache é do processo: cada teste começa vazio
    yield
    share._cache.clear()


def png(response) -> Image.Image:
    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(response.data))
    image.load()
    assert image.format == "PNG" and image.size == (cards.WIDTH, cards.HEIGHT) == (1200, 630)
    return image


def has_accent(image: Image.Image) -> bool:
    return any(
        all(abs(a - b) <= 6 for a, b in zip(pixel, ACCENT))
        for pixel in set(image.convert("RGB").getdata())
    )


def finish(client, rawg_id, start, end):
    response = client.put(f"/api/library/{rawg_id}", {"status": "zerado", "started_at": start, "completed_at": end})
    assert response.status_code in (200, 201), response.get_json()


def sql(app, query, params=()):
    connection = database.connect(app.config["DATABASE"])
    try:
        with connection:
            return connection.execute(query, params).fetchall()
    finally:
        connection.close()


class Spy:
    """Conta quantas vezes uma função de desenho foi chamada de verdade (o cache evita chamadas)."""

    def __init__(self, monkeypatch, name):
        self.calls: list[dict] = []
        original = getattr(cards, name)

        def wrapper(*args, **kwargs):
            self.calls.append({"args": args, "kwargs": kwargs})
            return original(*args, **kwargs)

        monkeypatch.setattr(cards, name, wrapper)


# --------------------------------------------------------------------------- imagem padrão
def test_default_card_is_a_branded_png_cached_publicly(api):
    response = api.get("/api/share/default.png")
    image = png(response)
    assert response.headers["Cache-Control"] == "public, max-age=600"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert has_accent(image)
    assert image.convert("RGB").getpixel((3, 3)) != (255, 255, 255)  # fundo escuro da marca, não branco


def test_cards_never_set_cookies_so_a_shared_cache_is_safe(ana):
    for path in ("/api/share/default.png", "/api/share/profile/ana.png"):
        response = ana.get(path)  # com a sessão da Ana
        assert response.status_code == 200
        assert "Set-Cookie" not in response.headers
        assert "cookie" not in response.headers.get("Vary", "").lower()


def test_cards_are_the_same_for_everyone(ana, bruno, api):
    finish(ana, HADES, "2025-01-01", "2025-01-10")
    bodies = {client_name: client.get("/api/share/profile/ana.png").data for client_name, client in
              (("ana", ana), ("bruno", bruno), ("visitante", api))}
    assert len(set(bodies.values())) == 1


def test_the_card_paths_need_the_png_extension_and_accept_only_get(api):
    assert api.get("/api/share/default").status_code == 404
    assert api.get("/api/share/profile/ana").status_code == 404
    response = api.post("/api/share/default.png")
    assert response.status_code == 405 and response.is_json


# --------------------------------------------------------------------------- perfil
def test_profile_card_is_a_valid_png_for_an_existing_user(ana, api):
    finish(ana, HADES, "2025-01-01", "2025-01-10")
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    image = png(api.get("/api/share/profile/ana.png"))
    assert has_accent(image)


def test_profile_card_of_an_unknown_user_is_a_json_404(api):
    response = api.get("/api/share/profile/ninguem.png")
    assert response.status_code == 404 and response.is_json
    assert response.get_json()["error"]["code"] == "not_found"


def test_profile_card_changes_when_what_is_drawn_changes(ana, api):
    first = api.get("/api/share/profile/ana.png").data
    ana.patch("/api/auth/me", {"bio": "Agora tenho uma biografia."})
    second = api.get("/api/share/profile/ana.png").data  # sem esperar o cache vencer
    assert first != second
    finish(ana, HADES, "2025-01-01", "2025-01-10")
    assert api.get("/api/share/profile/ana.png").data != second
    ana.patch("/api/auth/me", {"display_name": "Ana Souza"})
    assert png(api.get("/api/share/profile/ana.png"))


def test_each_profile_has_its_own_image(ana, bruno, api):
    assert api.get("/api/share/profile/ana.png").data != api.get("/api/share/profile/bruno.png").data


def test_unchanged_data_is_drawn_once_and_served_from_the_cache(ana, api, monkeypatch):
    spy = Spy(monkeypatch, "profile_card")
    for _ in range(3):
        assert api.get("/api/share/profile/ana.png").status_code == 200
    assert len(spy.calls) == 1
    ana.patch("/api/auth/me", {"bio": "mudou"})
    api.get("/api/share/profile/ana.png")
    assert len(spy.calls) == 2


def test_profile_card_counts_only_public_lists(ana, api, monkeypatch):
    spy = Spy(monkeypatch, "profile_card")
    ana.post("/api/lists", {"title": "Pública", "is_public": True})
    ana.post("/api/lists", {"title": "SEGREDO", "is_public": False})
    assert api.get("/api/share/profile/ana.png").status_code == 200
    assert spy.calls[0]["kwargs"]["stats"]["lists"] == 1
    assert "SEGREDO" not in str(spy.calls[0])


def test_profile_card_never_receives_email_or_other_private_fields(ana, api, monkeypatch):
    spy = Spy(monkeypatch, "profile_card")
    api.get("/api/share/profile/ana.png")
    assert "ana@exemplo.com" not in str(spy.calls[0]) and "password" not in str(spy.calls[0])


def test_uploaded_photo_appears_in_the_card_and_updates_it(ana, api):
    without = api.get("/api/share/profile/ana.png").data
    assert ana.upload("/api/auth/me/avatar", images.encode(images.two_halves(600, 600), "JPEG")).status_code == 200
    with_red_blue = api.get("/api/share/profile/ana.png")
    image = png(with_red_blue)
    assert with_red_blue.data != without
    colors = {image.convert("RGB").getpixel((x, 270)) for x in range(110, 310, 4)}  # linha que cruza a foto
    assert any(r > 150 and b < 100 for r, g, b in colors) and any(b > 150 and r < 100 for r, g, b in colors)

    assert ana.delete("/api/auth/me/avatar").status_code in (200, 204)
    assert api.get("/api/share/profile/ana.png").data == without  # voltou às iniciais


def test_a_corrupt_stored_photo_falls_back_to_initials_instead_of_failing(ana, api, app):
    ana.upload("/api/auth/me/avatar", images.encode(images.two_halves(300, 300), "PNG"))
    sql(app, "UPDATE user_avatars SET data = ?", (b"isto nao e uma imagem",))
    assert png(api.get("/api/share/profile/ana.png"))


@pytest.mark.parametrize(
    "display_name",
    [
        "田中太郎",  # alfabeto sem fonte embutida
        "Ana 😀🎮",  # emoji
        "مرحبا بالعالم",  # árabe
        "Ana " + "Sobrenome" * 5,  # nome no tamanho máximo, uma palavra só
        "José Ñandú — gamer",  # acentos e travessão
    ],
)
def test_names_in_any_alphabet_still_produce_a_valid_card(ana, api, display_name):
    assert ana.patch("/api/auth/me", {"display_name": display_name, "bio": "x"}).status_code == 200
    assert png(api.get("/api/share/profile/ana.png"))


@pytest.mark.parametrize(
    "bio",
    [
        "a" * 280,  # uma palavra enorme, sem espaço para quebrar
        "palavra " * 35,
        "linha um\n\n\nlinha dois\tcom tabulação",
        "日本語のプロフィールです。",
        "Gosto de 🎮 e de ☕",
        "<script>alert(1)</script> & \"aspas\"",
    ],
)
def test_awkward_bios_still_produce_a_valid_card(ana, api, bio):
    assert ana.patch("/api/auth/me", {"bio": bio}).status_code == 200
    assert png(api.get("/api/share/profile/ana.png"))


def test_a_long_username_with_a_long_name_fits(make_user, api):
    client = make_user("a" * 24, display_name="W" * 50)
    assert png(api.get(f"/api/share/profile/{'a' * 24}.png"))
    assert client.user["username"] == "a" * 24


# --------------------------------------------------------------------------- retrospectiva
def test_retrospective_card_is_a_valid_png_with_the_real_year(ana, api):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    finish(ana, CELESTE, "2025-05-01", "2025-05-04")
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    image = png(api.get("/api/share/retrospective/ana/2025.png"))
    assert has_accent(image)


def test_retrospective_card_for_a_year_without_records_is_404(ana, api):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    response = api.get("/api/share/retrospective/ana/2019.png")
    assert response.status_code == 404 and response.is_json
    assert response.headers["Cache-Control"] == "no-store"  # um 404 nunca fica em cache público


@pytest.mark.parametrize("year", [1999, 0, 9999])
def test_retrospective_card_rejects_years_out_of_range(ana, api, year):
    assert api.get(f"/api/share/retrospective/ana/{year}.png").status_code == 404


def test_retrospective_card_of_an_unknown_user_is_404(api):
    assert api.get("/api/share/retrospective/ninguem/2025.png").status_code == 404


def test_retrospective_card_changes_with_the_data(ana, api):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    first = api.get("/api/share/retrospective/ana/2025.png").data
    finish(ana, CELESTE, "2025-03-25", "2025-03-30")
    second = api.get("/api/share/retrospective/ana/2025.png").data
    assert first != second
    ana.post(f"/api/games/{CELESTE}/reviews", {"rating": 10})
    assert api.get("/api/share/retrospective/ana/2025.png").data != second


def test_retrospective_card_is_cached_and_ignores_private_lists(ana, api, monkeypatch):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    spy = Spy(monkeypatch, "retrospective_card")
    api.get("/api/share/retrospective/ana/2025.png")
    ana.post("/api/lists", {"title": "SEGREDO", "is_public": False})  # não entra em nada público
    api.get("/api/share/retrospective/ana/2025.png")
    assert len(spy.calls) == 1
    assert "SEGREDO" not in str(spy.calls[0]) and "ana@exemplo.com" not in str(spy.calls[0])


def test_retrospective_card_with_many_games_and_unusual_titles_still_renders(ana, api, app):
    finish(ana, HADES, "2025-01-05", "2025-01-06")
    finish(ana, CELESTE, "2025-02-05", "2025-02-06")
    sql(app, "UPDATE games SET name = ?", ("ゲーム " + "Título muito longo " * 8,))
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 10})
    assert png(api.get("/api/share/retrospective/ana/2025.png"))


# --------------------------------------------------------------------------- limites e falhas
def test_cards_are_rate_limited_per_ip(tmp_path):
    reset_rate_limits()
    limited = Api(create_app({"TESTING": True, "DATABASE": str(tmp_path / "r.db"), "RATELIMIT_ENABLED": True}))
    codes = [limited.get("/api/share/default.png").status_code for _ in range(125)]
    assert codes[:120] == [200] * 120 and set(codes[120:]) == {429}
    reset_rate_limits()


def test_without_pillow_the_card_routes_explain_what_is_missing(ana, api, monkeypatch):
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    monkeypatch.setitem(sys.modules, "PIL", None)  # `import PIL` passa a falhar, como numa instalação sem Pillow
    for path in ("/api/share/default.png", "/api/share/profile/ana.png", "/api/share/retrospective/ana/2025.png"):
        response = api.get(path)
        assert response.status_code == 503, path
        assert response.get_json()["error"]["code"] == "image_support_missing"
        assert response.headers["Cache-Control"] == "no-store"
    assert cards.available() is False


# --------------------------------------------------------------------------- texto desenhável
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ana", True),
        ("José Ñandú", True),
        ("Ana — gamer · 2025…", True),
        ("“aspas” e ‘aspas’", True),
        ("田中太郎", False),
        ("Ana 😀", False),
        ("مرحبا", False),
        ("tab\tdentro", True),  # espaços, tabulações e quebras de linha valem como um espaço
        ("linha um\n\nlinha dois", True),
        ("Ŧoni Ɓello", False),  # letras latinas raras que as fontes do site não têm
        ("ǅ ĸ ŉ", False),
        ("zero\u200blargura", False),  # invisíveis não vão para a imagem
        ("direita\u202epara a esquerda", False),  # nem o que inverte o sentido do texto
        ("hífen\u00admole", False),
        ("nulo\x00", False),
        ("", False),
        ("   ", False),
        (None, False),
    ],
)
def test_only_text_the_embedded_fonts_can_draw_is_drawn(text, expected):
    assert cards.supported(text) is expected


def test_a_name_with_letters_the_fonts_lack_falls_back_to_the_username():
    """Sem isso, a imagem sairia com quadradinhos no lugar das letras."""
    stats = {"games": 1, "by_status": {}, "average_rating": None}

    def name_row(display_name):
        data = cards.profile_card(display_name=display_name, username="ana", bio=None, stats=stats, avatar_bytes=None)
        return Image.open(io.BytesIO(data)).convert("RGB").crop((380, 120, 1150, 205))

    assert cards._display("Ŧoni Ɓello", "ana") == "@ana"
    assert cards._display("Ana Souza", "ana") == "Ana Souza"
    # A faixa do nome sai igual à de quem se chama literalmente "@ana": nenhuma letra sem desenho foi tentada.
    assert name_row("Ŧoni Ɓello").tobytes() == name_row("@ana").tobytes()
    assert name_row("Ana Souza").tobytes() != name_row("@ana").tobytes()


@pytest.mark.parametrize("value, expected", [(None, "–"), (9, "9"), (8.5, "8,5"), (8.25, "8,25"), (7.0, "7"), (0, "0"), (10, "10")])
def test_numbers_in_the_card_match_the_page(value, expected):
    assert cards._pt_number(value) == expected


# --------------------------------------------------------------------------- texto que não pode sair da imagem
BACKGROUND = (19, 19, 22)


def only_background(image: Image.Image, box: tuple[int, int, int, int], tolerance: int = 24) -> bool:
    """Nada além do fundo na faixa (a tolerância cobre o serrilhado suave da redução da imagem)."""
    extrema = image.convert("RGB").crop(box).getextrema()
    return all(low >= BACKGROUND[i] - tolerance and high <= BACKGROUND[i] + tolerance for i, (low, high) in enumerate(extrema))


def measure(text, max_lines=2, width=760):
    _, draw = cards._canvas()
    font = cards._font("read", cards._px(28))
    lines = cards._wrap(draw, text, font, width, max_lines)
    return draw, font, lines


def test_wrap_breaks_lines_by_words_and_marks_what_was_left_out():
    draw, font, lines = measure("palavra " * 40, max_lines=2)
    assert len(lines) == 2 and lines[-1].endswith("…") and not lines[0].endswith("…")
    assert all(draw.textlength(line, font=font) <= 760 * cards._SCALE for line in lines)
    _, _, short = measure("uma frase curta", max_lines=2)
    assert short == ["uma frase curta"]  # cabe: nada de reticências


def test_a_word_longer_than_the_line_is_cut_instead_of_leaving_the_image():
    draw, font, lines = measure("x" * 90)
    assert len(lines) == 1 and lines[0].endswith("…")
    assert draw.textlength(lines[0], font=font) <= 760 * cards._SCALE
    draw, font, lines = measure("antes " + "https://exemplo.com/" + "a" * 80 + " depois")
    assert all(draw.textlength(line, font=font) <= 760 * cards._SCALE for line in lines)
    assert all("……" not in line for line in lines)  # uma palavra cortada que cai na última linha não ganha reticências em dobro


def test_a_bio_with_one_huge_word_stays_inside_the_card(ana, api):
    ana.patch("/api/auth/me", {"bio": "https://exemplo.com/" + "a" * 90})
    image = png(api.get("/api/share/profile/ana.png"))
    assert only_background(image, (1150, 300, 1200, 420))  # a faixa à direita do texto, onde ele estouraria


def test_a_long_name_ends_before_the_month_chart_of_the_retrospective(ana, api):
    ana.patch("/api/auth/me", {"display_name": "Ana Maria da Silva Sauro Pereira Gamer"})
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    image = png(api.get("/api/share/retrospective/ana/2025.png"))
    assert only_background(image, (675, 110, 696, 175))  # o nome termina antes do rótulo do gráfico (x=700)


def test_each_card_route_has_its_own_rate_limit_check(tmp_path):
    for path in ("/api/share/profile/ana.png", "/api/share/retrospective/ana/2025.png"):
        reset_rate_limits()
        limited = Api(create_app({"TESTING": True, "DATABASE": str(tmp_path / f"{abs(hash(path))}.db"), "RATELIMIT_ENABLED": True}))
        limited.register("ana")
        limited.put("/api/library/%d" % HADES, {"status": "zerado", "started_at": "2025-03-01", "completed_at": "2025-03-20"})
        codes = [limited.get(path).status_code for _ in range(125)]
        assert 429 in codes[120:] and codes[:100].count(429) == 0, path
    reset_rate_limits()


def test_a_retrospective_with_only_an_abandoned_game_still_draws(ana, api):
    assert ana.put(f"/api/library/{HADES}", {"status": "abandonado"}).status_code in (200, 201)
    year = __import__("app.utils.dates", fromlist=["today_utc"]).today_utc().year
    assert png(api.get(f"/api/share/retrospective/ana/{year}.png"))


def test_a_bio_with_letters_the_fonts_lack_is_left_out_of_the_card():
    stats = {"games": 1, "by_status": {}, "average_rating": None}

    def bio_area(bio):
        data = cards.profile_card(display_name="Ana", username="ana", bio=bio, stats=stats, avatar_bytes=None)
        return Image.open(io.BytesIO(data)).convert("RGB").crop((380, 290, 1150, 420))

    assert bio_area("Ŧoni Ɓello joga tudo").tobytes() == bio_area(None).tobytes()
    assert bio_area("Joga de tudo um pouco").tobytes() != bio_area(None).tobytes()
