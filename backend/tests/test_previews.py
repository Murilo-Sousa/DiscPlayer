"""Prévia de links: o que robôs (WhatsApp, Discord, LinkedIn...) leem no HTML ao receber um endereço do site.

Esses robôs não executam JavaScript, então título, descrição e imagem são colocados no `index.html`
pelo servidor (`routes/spa.py` + `services/previews.py`). Aqui o `index.html` é uma cópia do
`frontend/index.html` do repositório, que é a base real do build.
"""
from __future__ import annotations

import os
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import create_app
from app import db as database
from app.routes import spa as spa_routes
from app.security import reset_rate_limits
from app.services import cards, previews, rawg
from app.utils.dates import today_utc

from . import fake_rawg
from .conftest import CELESTE, HADES, Api

REPO_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
THIS_YEAR = today_utc().year
BASE = "http://localhost"
SITE_DESCRIPTION = previews.DEFAULT_DESCRIPTION


class Head(HTMLParser):
    """Lê o que um robô leria: <title>, <meta> e <link>. O texto já vem sem o escape de HTML."""

    def __init__(self, text: str):
        super().__init__()
        self.titles: list[str] = []
        self.metas: list[tuple[str, str, str]] = []  # (atributo, nome, conteúdo)
        self.links: list[dict] = []
        self._in_title = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
            self.titles.append("")
        elif tag == "meta":
            for key in ("name", "property"):
                if key in attrs:
                    self.metas.append((key, attrs[key], attrs.get("content", "")))
        elif tag == "link":
            self.links.append(attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.titles[-1] += data

    def all(self, name: str) -> list[str]:
        return [content for _, meta_name, content in self.metas if meta_name == name]

    def one(self, name: str) -> str:
        found = self.all(name)
        assert len(found) == 1, f"esperava exatamente um {name}, veio {found}"
        return found[0]

    @property
    def title(self) -> str:
        assert len(self.titles) == 1, f"esperava um só <title>, vieram {self.titles}"
        return self.titles[0]


def head_of(response) -> Head:
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    return Head(response.get_data(as_text=True))


def build_dist(tmp_path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    shutil.copy(REPO_INDEX, dist / "index.html")
    return dist


def make_site(tmp_path, **config) -> Api:
    reset_rate_limits()  # os contadores ficam na memória do processo: cada teste começa do zero
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "site.db"),
            "RATELIMIT_ENABLED": False,
            "RAWG_API_KEY": "chave-de-teste",
            "FRONTEND_DIST": str(build_dist(tmp_path)),
            **config,
        }
    )
    return Api(app)


@pytest.fixture
def site(tmp_path, monkeypatch) -> Api:
    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    rawg.clear_cache()
    yield make_site(tmp_path)
    rawg.clear_cache()


def sql(site, query, params=()):
    connection = database.connect(site.client.application.config["DATABASE"])
    try:
        with connection:
            return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def register(site, username="ana", **extra) -> Api:
    client = Api(site.client.application)
    client.register(username, **extra)
    return client


def finish(client, rawg_id, start="2025-03-01", end="2025-03-20"):
    response = client.put(f"/api/library/{rawg_id}", {"status": "zerado", "started_at": start, "completed_at": end})
    assert response.status_code in (200, 201), response.get_json()


def make_list(client, title="Melhores indies", **extra):
    response = client.post("/api/lists", {"title": title, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["list"]


def add_game(client, list_id, rawg_id):
    assert client.post(f"/api/lists/{list_id}/games", {"rawg_id": rawg_id}).status_code in (200, 201)


def default_image(base=BASE):
    return f"{base}/api/share/default.png"


# --------------------------------------------------------------------------- página padrão e estrutura
def test_every_page_has_the_default_preview_with_absolute_urls(site):
    for path in ("/", "/jogos", "/entrar", "/qualquer-rota-do-react"):
        head = head_of(site.get(path))
        assert head.title == "DiscPlayer"
        assert head.one("description") == SITE_DESCRIPTION
        assert head.one("og:title") == "DiscPlayer" and head.one("og:site_name") == "DiscPlayer"
        assert head.one("og:type") == "website" and head.one("og:locale") == "pt_BR"
        assert head.one("og:image") == default_image() == head.one("twitter:image")
        assert head.one("og:image:width") == "1200" and head.one("og:image:height") == "630"
        assert head.one("twitter:card") == "summary_large_image"
        assert head.one("og:image:alt") == head.one("twitter:image:alt") != ""


def test_the_original_title_and_description_are_replaced_not_duplicated(site):
    head = head_of(site.get("/u/ana"))  # usuária inexistente: prévia padrão, ainda assim sem duplicatas
    assert len(head.titles) == 1 and len(head.all("description")) == 1
    assert len(head.all("og:title")) == len(head.all("og:description")) == len(head.all("og:image")) == 1
    assert len([link for link in head.links if link.get("rel") == "canonical"]) == 1


def test_the_rest_of_index_html_is_kept_as_it_was_built(site):
    text = site.get("/").get_data(as_text=True)
    for original in ('<div id="root"></div>', 'name="theme-color"', 'rel="icon"', 'src="/src/main.jsx"', "<noscript>"):
        assert original in text
    assert text.count("</head>") == 1 and text.index("og:image") < text.index("</head>")


def test_canonical_and_og_url_use_the_path_without_the_query_string(site):
    head = head_of(site.get("/jogos?q=zelda&utm_source=teste"))
    assert head.one("og:url") == f"{BASE}/jogos"
    assert [link["href"] for link in head.links if link.get("rel") == "canonical"] == [f"{BASE}/jogos"]
    assert "utm_source" not in site.get("/jogos?utm_source=teste").get_data(as_text=True)


def test_security_headers_and_no_cache_stay_on_the_html(site):
    response = site.get("/u/ana")
    assert response.headers["Cache-Control"] == "no-cache"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_a_built_index_without_head_still_gets_the_tags(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>x</title><div id=root></div>")
    client = Api(create_app({"TESTING": True, "DATABASE": str(tmp_path / "x.db"), "FRONTEND_DIST": str(dist)}))
    head = head_of(client.get("/"))
    assert head.title == "DiscPlayer" and head.one("og:image") == default_image()


def test_index_html_is_reread_when_a_new_build_replaces_it(site, tmp_path):
    index = tmp_path / "dist" / "index.html"
    assert "novo-build" not in site.get("/").get_data(as_text=True)
    index.write_text(index.read_text().replace('<div id="root">', '<div id="novo-build"><div id="root">'))
    stamp = index.stat().st_mtime_ns + 5_000_000_000  # garante um mtime diferente em qualquer sistema de arquivos
    os.utime(index, ns=(stamp, stamp))
    assert "novo-build" in site.get("/").get_data(as_text=True)


def test_assets_are_still_served_untouched(site, tmp_path):
    (tmp_path / "dist" / "assets" / "app-abc123.js").write_text("console.log('ok')")
    response = site.get("/assets/app-abc123.js")
    assert response.get_data(as_text=True) == "console.log('ok')"
    assert "og:title" not in response.get_data(as_text=True)


# --------------------------------------------------------------------------- endereço absoluto
def test_without_public_url_the_request_host_is_used(site):
    response = site.get("/", base_url="http://meu-pc.local:5000")
    head = head_of(response)
    assert head.one("og:image") == "http://meu-pc.local:5000/api/share/default.png"
    assert head.one("og:url") == "http://meu-pc.local:5000/"


def test_public_url_wins_over_the_request_host(tmp_path, monkeypatch):
    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    client = make_site(tmp_path, PUBLIC_URL="https://discplayer.exemplo.com")
    register_client = Api(client.client.application)
    register_client.register("ana")
    response = client.get("/u/ana", base_url="http://host-falso.invalid")
    head = head_of(response)
    assert head.one("og:url") == "https://discplayer.exemplo.com/u/ana"
    assert head.one("og:image").startswith("https://discplayer.exemplo.com/api/share/profile/ana.png")
    assert "host-falso" not in response.get_data(as_text=True)  # um Host forjado não vira link na página


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://discplayer.exemplo.com/", "https://discplayer.exemplo.com"),
        ("  http://localhost:8080  ", "http://localhost:8080"),
        ("discplayer.exemplo.com", ""),  # sem http(s)
        ("javascript:alert(1)", ""),
        ("ftp://exemplo.com", ""),
        ("https://exemplo.com/subpasta", ""),  # com caminho: ambíguo, ignora
        ("https://", ""),
        ("", ""),
    ],
)
def test_public_url_is_validated(monkeypatch, raw, expected):
    from app.config import build_config

    monkeypatch.setenv("PUBLIC_URL", raw)
    assert build_config()["PUBLIC_URL"] == expected


# --------------------------------------------------------------------------- jogos
def test_game_preview_uses_the_local_copy_with_year_and_https_cover(site):
    ana = register(site)
    finish(ana, HADES)  # guarda a cópia local do jogo
    head = head_of(site.get(f"/jogos/{HADES}-hades"))
    assert head.title == "Hades · DiscPlayer"
    assert head.one("og:title") == "Hades · DiscPlayer"
    assert "Lançado em 2020." in head.one("description")
    assert head.one("og:image") == "https://media.rawg.io/media/games/fake/hades.jpg"
    assert head.one("og:image:alt") == "Capa de Hades"
    assert head.one("og:url") == f"{BASE}/jogos/{HADES}-hades"
    assert head.all("og:image:width") == []  # o tamanho da capa da RAWG não é conhecido


def test_game_preview_shows_the_community_average_only_with_real_reviews(site):
    ana, bruno = register(site, "ana"), register(site, "bruno")
    finish(ana, HADES)
    assert "Registre, avalie e escreva sobre Hades" in head_of(site.get(f"/jogos/{HADES}")).one("description")
    assert "Nota média" not in head_of(site.get(f"/jogos/{HADES}")).one("description")

    for client, rating in ((ana, 9), (bruno, 8)):
        assert client.post(f"/api/games/{HADES}/reviews", {"rating": rating}).status_code == 201
    description = head_of(site.get(f"/jogos/{HADES}")).one("description")
    assert "Nota média da comunidade DiscPlayer: 8,5 em 2 avaliações." in description


def test_game_preview_never_includes_review_text(site):
    ana = register(site)
    finish(ana, HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "SEGREDO-DO-FINAL-DO-JOGO"})
    text = site.get(f"/jogos/{HADES}").get_data(as_text=True)
    assert "SEGREDO-DO-FINAL-DO-JOGO" not in text


def test_game_not_stored_locally_is_read_from_the_rawg_cache(site):
    assert site.get(f"/api/games/{CELESTE}").status_code == 200  # a página do jogo faz isso ao abrir
    head = head_of(site.get(f"/jogos/{CELESTE}-celeste"))  # ninguém registrou o jogo
    assert head.title == "Celeste · DiscPlayer"
    assert "Registre, avalie e escreva sobre Celeste" in head.one("description")
    assert head.one("og:image") == "https://media.rawg.io/media/games/fake/celeste.jpg"


def test_previews_never_call_the_rawg(site, monkeypatch):
    """Um robô que percorre endereços de jogos não pode gastar a cota da RAWG nem deixar a página lenta."""
    calls = []

    def spy(path, params=None):
        calls.append(path)
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", spy)
    rawg.clear_cache()
    for rawg_id in (CELESTE, HADES, 987654321, 1, 2, 3):
        head = head_of(site.get(f"/jogos/{rawg_id}-qualquer-coisa"))
        assert head.title == "DiscPlayer"  # sem cache e sem cópia local: prévia padrão
    assert calls == []


def test_an_expired_rawg_cache_entry_still_makes_the_preview(site):
    assert site.get(f"/api/games/{CELESTE}").status_code == 200
    cache = rawg._cache
    key = ("game", CELESTE)
    value = cache.get(key)
    cache.set(key, value, ttl=0.0, stale_ttl=3600)  # expirou, mas ainda dentro da tolerância
    assert cache.get(key) is None
    assert head_of(site.get(f"/jogos/{CELESTE}")).title == "Celeste · DiscPlayer"


def test_unknown_game_gets_the_default_preview(site):
    for path in ("/jogos/999999999", "/jogos/999999999-nao-existe"):
        head = head_of(site.get(path))
        assert head.title == "DiscPlayer" and head.one("og:image") == default_image()
        assert "999999999" not in head.title


def test_rawg_down_does_not_matter_to_the_preview_and_the_page_still_opens(site, monkeypatch):
    def down(path, params=None):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    rawg.clear_cache()
    response = site.get(f"/jogos/{CELESTE}-celeste")
    head = head_of(response)
    assert head.title == "DiscPlayer" and head.one("og:image") == default_image()
    assert 'id="root"' in response.get_data(as_text=True)


def test_game_paths_that_are_not_games_get_the_default_preview(site):
    for path in ("/jogos/abc", "/jogos/12abc", "/jogos/1234567890123", "/jogos/-5", "/jogos/12/extra"):
        assert head_of(site.get(path)).title == "DiscPlayer", path


@pytest.mark.parametrize("cover", ["http://insegura.exemplo/capa.jpg", "javascript:alert(1)", "//exemplo.com/c.jpg", "", None])
def test_only_https_covers_are_used_otherwise_the_site_image(site, cover):
    ana = register(site)
    finish(ana, HADES)
    sql(site, "UPDATE games SET cover_url = ?", (cover,))
    head = head_of(site.get(f"/jogos/{HADES}"))
    assert head.one("og:image") == default_image()
    assert head.one("og:image:alt") == "O logotipo do DiscPlayer: um disco com um quarto preenchido."
    assert head.title == "Hades · DiscPlayer"


def test_game_name_with_markup_cannot_break_the_page(site):
    ana = register(site)
    finish(ana, HADES)
    evil = 'Hades"><script>alert(1)</script><meta x="'
    sql(site, "UPDATE games SET name = ?", (evil,))
    response = site.get(f"/jogos/{HADES}")
    text = response.get_data(as_text=True)
    assert "<script>alert(1)" not in text and '"><script' not in text
    head = head_of(response)
    assert head.title == f"{evil} · DiscPlayer"  # o texto original, só que escapado no HTML
    assert head.one("og:title") == head.title


# --------------------------------------------------------------------------- perfis
def test_profile_preview_has_name_numbers_and_bio(site):
    ana = register(site, display_name="Ana Souza")
    ana.patch("/api/auth/me", {"bio": "Jogo de tudo.\nPrincipalmente RPG."})
    finish(ana, HADES)
    finish(ana, CELESTE)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    head = head_of(site.get("/u/ana"))
    assert head.title == "Ana Souza (@ana) · DiscPlayer"
    description = head.one("description")
    assert description.startswith("2 jogos no diário · 2 zerados · nota média 9.")
    assert "Jogo de tudo. Principalmente RPG." in description and "\n" not in description
    assert head.one("og:image") == f"{BASE}/api/share/profile/ana.png"
    assert head.one("og:image:width") == "1200"


def test_profile_preview_uses_singular_and_handles_an_empty_diary(site):
    ana = register(site)
    assert head_of(site.get("/u/ana")).one("description") == "ana está no DiscPlayer."
    finish(ana, HADES)
    assert head_of(site.get("/u/ana")).one("description").startswith("1 jogo no diário · 1 zerado")


def test_profile_preview_never_exposes_email_or_private_data(site):
    ana = register(site, email="ana.secreta@exemplo.com")
    finish(ana, HADES)
    make_list(ana, "LISTA-PRIVADA-DA-ANA", is_public=False)
    text = site.get("/u/ana").get_data(as_text=True)
    assert "ana.secreta" not in text and "LISTA-PRIVADA-DA-ANA" not in text


def test_profile_text_with_markup_cannot_break_the_page(site):
    ana = register(site)
    evil_name = 'Ana"><script>alert(1)</script>'
    evil_bio = "<img src=x onerror=alert(1)> & 'aspas' \"duplas\""
    assert ana.patch("/api/auth/me", {"display_name": evil_name, "bio": evil_bio}).status_code == 200
    response = site.get("/u/ana")
    text = response.get_data(as_text=True)
    assert "<script>alert(1)" not in text and "<img src=x" not in text
    head = head_of(response)
    assert head.title == f"{evil_name} (@ana) · DiscPlayer"
    assert evil_bio in head.one("description")


def test_unknown_user_gets_the_default_preview_and_does_not_reveal_anything(site):
    head = head_of(site.get("/u/ninguem"))
    assert head.title == "DiscPlayer" and head.one("og:image") == default_image()
    assert "ninguem" not in head.one("og:title")


@pytest.mark.parametrize("path", ["/u/ab", "/u/" + "a" * 25, "/u/ana%20x", "/u/a-b-c", "/u/ana/seguindo"])
def test_user_paths_with_invalid_usernames_get_the_default_preview(site, path):
    register(site)
    assert head_of(site.get(path)).title == "DiscPlayer"


def test_long_bio_is_cut_in_the_description(site):
    ana = register(site)
    ana.patch("/api/auth/me", {"bio": "palavra " * 35})  # 280 caracteres, o máximo permitido
    description = head_of(site.get("/u/ana")).one("description")
    assert len(description) <= previews.DESCRIPTION_LIMIT and description.endswith("…")


# --------------------------------------------------------------------------- listas
def test_public_list_preview_has_title_owner_description_and_first_cover(site):
    ana = register(site, display_name="Ana Souza")
    lst = make_list(ana, "Melhores indies", description="Para jogar com calma.")
    add_game(ana, lst["id"], CELESTE)
    add_game(ana, lst["id"], HADES)
    head = head_of(site.get(f"/listas/{lst['id']}"))
    assert head.title == "Melhores indies · lista de Ana Souza · DiscPlayer"
    assert head.one("description") == "Lista de Ana Souza. Para jogar com calma."
    assert head.one("og:image") == "https://media.rawg.io/media/games/fake/celeste.jpg"  # a primeira da ordem da lista
    assert head.one("og:image:alt") == "Capa de Celeste"


def test_public_list_without_description_counts_its_games(site):
    ana = register(site)
    lst = make_list(ana, "Vazia")
    assert head_of(site.get(f"/listas/{lst['id']}")).one("description") == "Lista de ana. Uma lista de jogos."
    add_game(ana, lst["id"], HADES)
    assert head_of(site.get(f"/listas/{lst['id']}")).one("description") == "Lista de ana. 1 jogo nesta lista."


def test_private_list_is_indistinguishable_from_one_that_does_not_exist(site):
    ana = register(site)
    lst = make_list(ana, "SEGREDO-PRIVADO", description="Ninguém pode ver", is_public=False)
    add_game(ana, lst["id"], HADES)

    anonymous = site.get(f"/listas/{lst['id']}")
    nonexistent = site.get("/listas/987654")
    for response in (anonymous, ana.get(f"/listas/{lst['id']}")):  # o robô não tem cookie, mas nem a dona vê
        text = response.get_data(as_text=True)
        assert "SEGREDO-PRIVADO" not in text and "Ninguém pode ver" not in text
        assert head_of(response).title == "DiscPlayer"
    assert head_of(anonymous).all("og:title") == head_of(nonexistent).all("og:title")
    assert head_of(anonymous).one("og:image") == default_image()


def test_a_list_turned_private_stops_being_previewed(site):
    ana = register(site)
    lst = make_list(ana, "Era pública")
    assert head_of(site.get(f"/listas/{lst['id']}")).title.startswith("Era pública")
    assert ana.patch(f"/api/lists/{lst['id']}", {"is_public": False}).status_code == 200
    assert head_of(site.get(f"/listas/{lst['id']}")).title == "DiscPlayer"


def test_list_text_with_markup_cannot_break_the_page(site):
    ana = register(site)
    lst = make_list(ana, 'Lista"><script>alert(1)</script>', description="<b onmouseover=alert(1)>oi</b>")
    response = site.get(f"/listas/{lst['id']}")
    text = response.get_data(as_text=True)
    assert "<script>alert(1)" not in text and "<b onmouseover" not in text
    assert head_of(response).title.startswith('Lista"><script>alert(1)</script>')


def test_list_paths_that_are_not_lists_get_the_default_preview(site):
    for path in ("/listas", "/listas/abc", "/listas/1/editar", "/listas/0"):
        assert head_of(site.get(path)).title == "DiscPlayer", path


# --------------------------------------------------------------------------- retrospectiva
def test_retrospective_preview_summarizes_the_year(site):
    ana = register(site, display_name="Ana Souza")
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    finish(ana, CELESTE, "2025-05-01", "2025-05-04")
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    sql(site, "UPDATE reviews SET created_at = '2025-03-21T10:00:00+00:00'")
    head = head_of(site.get("/u/ana/retrospectiva/2025"))
    assert head.title == "Retrospectiva 2025 de Ana Souza · DiscPlayer"
    description = head.one("description")
    assert "2 jogos zerados" in description and "nota média 9" in description and "jogo do ano: Hades" in description
    assert head.one("og:image") == f"{BASE}/api/share/retrospective/ana/2025.png"
    assert head.one("og:image:width") == "1200" and head.one("og:image:height") == "630"


def test_retrospective_without_year_uses_the_latest_year_with_data(site):
    ana = register(site)
    finish(ana, HADES, "2023-01-01", "2023-01-10")
    finish(ana, CELESTE, "2024-02-01", "2024-02-10")
    for path in ("/u/ana/retrospectiva", "/u/ana/retrospectiva/"):
        head = head_of(site.get(path))
        assert head.title == "Retrospectiva 2024 de ana · DiscPlayer"
        assert head.one("og:image").endswith("/api/share/retrospective/ana/2024.png")


def test_current_year_preview_says_it_is_partial(site):
    ana = register(site)
    today = today_utc().isoformat()  # o servidor recusa datas além de amanhã: usa hoje, que é sempre do ano atual
    finish(ana, HADES, today, today)
    assert "(até agora)" in head_of(site.get(f"/u/ana/retrospectiva/{THIS_YEAR}")).title


def test_retrospective_of_an_empty_year_falls_back_to_the_profile_preview(site):
    ana = register(site)
    finish(ana, HADES, "2023-01-01", "2023-01-10")
    head = head_of(site.get("/u/ana/retrospectiva/2019"))
    assert head.title == "ana (@ana) · DiscPlayer"
    assert head.one("og:image").endswith("/api/share/profile/ana.png")  # nunca aponta para uma imagem que daria 404


def test_retrospective_of_an_account_with_no_data_uses_the_profile_preview(site):
    register(site)
    assert head_of(site.get("/u/ana/retrospectiva")).title == "ana (@ana) · DiscPlayer"


@pytest.mark.parametrize("year", ["1999", "0000", str(THIS_YEAR + 2), "9999"])
def test_retrospective_years_out_of_range_get_the_default_preview(site, year):
    register(site)
    assert head_of(site.get(f"/u/ana/retrospectiva/{year}")).title == "DiscPlayer"


def test_retrospective_of_an_unknown_user_gets_the_default_preview(site):
    assert head_of(site.get("/u/ninguem/retrospectiva/2025")).title == "DiscPlayer"


def test_retrospective_preview_ignores_private_lists(site):
    ana = register(site)
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    make_list(ana, "SEGREDO-PRIVADO", is_public=False)
    assert "SEGREDO-PRIVADO" not in site.get("/u/ana/retrospectiva/2025").get_data(as_text=True)


# --------------------------------------------------------------------------- robustez
def test_a_failure_while_building_the_preview_never_breaks_the_page(site, monkeypatch):
    register(site)

    def boom(*args, **kwargs):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(previews.profiles_service, "get_by_username", boom)
    response = site.get("/u/ana")
    assert response.status_code == 200 and 'id="root"' in response.get_data(as_text=True)
    assert head_of(response).title == "DiscPlayer"


def test_without_pillow_the_page_has_text_previews_and_no_broken_image(site, monkeypatch):
    ana = register(site)
    monkeypatch.setattr(cards, "available", lambda: False)
    head = head_of(site.get("/u/ana"))
    assert head.title == "ana (@ana) · DiscPlayer"
    assert head.all("og:image") == [] and head.all("twitter:image") == []
    assert head.one("twitter:card") == "summary"
    finish(ana, HADES)  # a capa da RAWG continua valendo sem o Pillow
    assert head_of(site.get(f"/jogos/{HADES}")).one("og:image").startswith("https://media.rawg.io/")


def test_dynamic_previews_are_rate_limited_and_fall_back_to_the_default(tmp_path, monkeypatch):
    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    limited = make_site(tmp_path, RATELIMIT_ENABLED=True)
    Api(limited.client.application).register("ana")

    limit = spa_routes.PREVIEW_LIMIT
    titles = [head_of(limited.get("/u/ana")).title for _ in range(limit + 5)]
    assert titles[0] == "ana (@ana) · DiscPlayer" and titles[limit - 1] == "ana (@ana) · DiscPlayer"
    assert set(titles[limit:]) == {"DiscPlayer"}  # passou do limite: não consulta o banco, mas a página abre
    assert head_of(limited.get("/jogos")).title == "DiscPlayer"  # rotas sem consulta não gastam o limite


def test_static_routes_do_not_spend_the_preview_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    limited = make_site(tmp_path, RATELIMIT_ENABLED=True)
    Api(limited.client.application).register("ana")
    for _ in range(spa_routes.PREVIEW_LIMIT + 50):
        assert limited.get("/entrar").status_code == 200
    assert head_of(limited.get("/u/ana")).title == "ana (@ana) · DiscPlayer"


def test_the_preview_does_not_depend_on_who_is_logged_in(site):
    ana, bruno = register(site, "ana"), register(site, "bruno")
    lst = make_list(ana, "Privada da Ana", is_public=False)
    finish(ana, HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 7, "body": "texto particular"})
    seen = {client_name: head_of(client.get(f"/listas/{lst['id']}")).title for client_name, client in
            (("ana", ana), ("bruno", bruno), ("visitante", site))}
    assert set(seen.values()) == {"DiscPlayer"}


# --------------------------------------------------------------------------- funções internas
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  várias\n linhas\t e   espaços ", "várias linhas e espaços"),
        ("com\x00controle\x07", "com controle"),
        (None, ""),
        ("", ""),
        ("a" * 50, "a" * 50),
    ],
)
def test_clean_flattens_text(raw, expected):
    assert previews._clean(raw, 100) == expected


def test_clean_cuts_at_the_limit_with_an_ellipsis():
    cut = previews._clean("abcdefghij " * 5, 20)
    assert len(cut) <= 20 and cut.endswith("…")


@pytest.mark.parametrize(
    "value, expected", [(None, ""), (9, "9"), (8.5, "8,5"), (7.25, "7,25"), (8.33, "8,33"), (0, "0"), (10.0, "10")]
)
def test_numbers_use_the_brazilian_decimal_comma_and_up_to_two_digits(value, expected):
    assert previews._number(value) == expected


@pytest.mark.parametrize(
    "path, dynamic",
    [
        ("jogos/12", True), ("/jogos/12-hades/", True), ("u/ana", True), ("u/ana/retrospectiva", True),
        ("u/ana/retrospectiva/2025", True), ("listas/3", True),
        ("", False), ("jogos", False), ("listas", False), ("entrar", False), ("u/ana/seguindo", False),
        ("assets/app.js", False),
    ],
)
def test_is_dynamic_only_for_paths_that_hit_the_database(path, dynamic):
    assert previews.is_dynamic(path) is dynamic


# --------------------------------------------------------------------------- revisão: regras que faltavam
ARABIC_INDIC = "٢٠٢٥"  # "2025" em dígitos árabes-índicos: \d do Python os aceitaria


def test_only_ascii_digits_make_a_site_address(site):
    ana = register(site)
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    lst = make_list(ana, "Pública")
    arabic_id = "".join(chr(0x0660 + int(digit)) for digit in str(lst["id"]))
    for path in (
        f"/jogos/{''.join(chr(0x0660 + int(d)) for d in str(HADES))}",
        f"/listas/{arabic_id}",
        f"/u/ana/retrospectiva/{ARABIC_INDIC}",
    ):
        assert head_of(site.get(path)).title == "DiscPlayer", path
    assert head_of(site.get(f"/listas/{lst['id']}")).title.startswith("Pública")  # o mesmo endereço em ASCII funciona
    assert not previews.is_dynamic(f"jogos/{arabic_id}") and not previews.is_dynamic(f"u/ana/retrospectiva/{ARABIC_INDIC}")


def test_emoji_sequences_survive_in_names_and_bios(site):
    ana = register(site)
    family = "👨‍👩‍👧"
    flag = "🏳️‍🌈"
    assert ana.patch("/api/auth/me", {"display_name": f"Ana {family}", "bio": f"Orgulho {flag}"}).status_code == 200
    head = head_of(site.get("/u/ana"))
    assert family in head.title and flag in head.one("description")


@pytest.mark.parametrize("raw", ["Ana‮x", "Ana\x00x", "Ana​x", "Ana\x07x"])
def test_other_invisible_and_control_characters_are_replaced_by_a_space(raw):
    assert previews._clean(raw, 100) == "Ana x"


def test_a_list_cover_that_is_not_https_is_not_used(site):
    ana = register(site)
    lst = make_list(ana, "Com capa insegura")
    add_game(ana, lst["id"], HADES)
    sql(site, "UPDATE games SET cover_url = 'http://insegura.exemplo/capa.jpg'")
    head = head_of(site.get(f"/listas/{lst['id']}"))
    assert head.one("og:image") == default_image() and head.title.startswith("Com capa insegura")
    assert head.one("og:image:alt") == previews.DEFAULT_IMAGE_ALT


def test_preview_text_is_cut_at_its_limits(site):
    ana = register(site, display_name="N" * 50)
    lst = make_list(ana, "T" * 80, description="d " * 100)
    head = head_of(site.get(f"/listas/{lst['id']}"))
    # O corte cai no limite (ou um ou dois caracteres antes, se terminaria em espaço) e termina com reticências.
    assert previews.TITLE_LIMIT - 2 <= len(head.title) <= previews.TITLE_LIMIT and head.title.endswith("…")
    description = head.one("description")
    assert previews.DESCRIPTION_LIMIT - 2 <= len(description) <= previews.DESCRIPTION_LIMIT and description.endswith("…")
    assert head.one("og:title") == head.title


def test_the_profile_bio_is_cut_at_120_characters(site):
    ana = register(site)
    ana.patch("/api/auth/me", {"bio": "palavra " * 35})
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    bio_part = head_of(site.get("/u/ana")).one("description").split(". ", 1)[1]
    assert len(bio_part) == 120 and bio_part.endswith("…")


def test_the_average_in_the_preview_is_the_one_the_page_shows(site):
    ana, bruno = register(site, "ana"), register(site, "bruno")
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    finish(ana, CELESTE, "2025-04-01", "2025-04-02")
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 8})
    ana.post(f"/api/games/{CELESTE}/reviews", {"rating": 8.5})
    assert ana.get("/api/users/ana").get_json()["stats"]["average_rating"] == 8.25  # a página mostra "8,25"
    assert "nota média 8,25" in head_of(site.get("/u/ana")).one("description")
    finish(bruno, HADES, "2025-03-01", "2025-03-20")
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    bruno.post(f"/api/games/{CELESTE}/reviews", {"rating": 8})
    assert "Nota média da comunidade DiscPlayer: 8,5 em 2 avaliações." in head_of(site.get(f"/jogos/{HADES}")).one("description")


def test_a_zero_rated_year_has_no_game_of_the_year_in_the_preview(site):
    ana = register(site)
    finish(ana, HADES, "2025-03-01", "2025-03-20")
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 0})
    sql(site, "UPDATE reviews SET created_at = '2025-03-21T10:00:00+00:00'")
    assert "jogo do ano" not in head_of(site.get("/u/ana/retrospectiva/2025")).one("description")
