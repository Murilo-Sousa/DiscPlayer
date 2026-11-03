"""Filtro de conteúdo adulto: a RAWG lista jogos 18+ e o DiscPlayer os esconde (ADULT_CONTENT_FILTER)."""
from __future__ import annotations

import pytest

from app.config import build_config
from app.services import adult, games as games_service, rawg

from . import fake_rawg
from .conftest import CELESTE, HADES

ONLY_ESRB = fake_rawg.by_name("Jardim Proibido")["id"]  # ESRB Adults Only, sem tags explícitas
ONLY_TAG = fake_rawg.by_name("Noite Sem Censura")["id"]  # sem classificação, tag nsfw
HENTAI_TAG = fake_rawg.by_name("Quarto Dezoito")["id"]  # sem classificação, tags hentai e nudity
ADULT = [ONLY_ESRB, ONLY_TAG, HENTAI_TAG]
WITCHER = fake_rawg.by_name("The Witcher 3: Wild Hunt")["id"]  # ESRB Mature + tags de nudez e conteúdo sexual


def use_level(app, level):
    """Muda o nível do filtro em tempo de execução (o cache guarda o que foi decidido antes)."""
    app.config["ADULT_CONTENT_FILTER"] = level
    rawg.clear_cache()


def names(response):
    return [game["name"] for game in response.get_json()["results"]]


def raw(esrb=None, *tags):
    return {
        "id": 1,
        "esrb_rating": {"slug": esrb, "name": esrb} if esrb else None,
        "tags": [{"slug": slug, "name": slug} for slug in tags],
    }


# ------------------------------------------------------------------------------ a decisão
@pytest.mark.parametrize(
    "game, explicit, mature",
    [
        (raw("adults-only"), True, True),
        (raw(None, "nsfw"), True, True),
        (raw(None, "singleplayer", "hentai"), True, True),
        (raw(None, "eroge"), True, True),
        (raw(None, "erotic"), True, True),
        (raw("mature"), False, True),  # 17+ não é 18+: só o nível mais rígido
        (raw("mature", "nudity"), False, True),
        (raw("teen", "sexual-content"), False, True),
        (raw("everyone", "singleplayer"), False, False),
        (raw(), False, False),
    ],
)
def test_each_level_hides_what_it_promises(game, explicit, mature):
    assert adult.is_blocked(game, "explicit") is explicit
    assert adult.is_blocked(game, "mature") is mature
    assert adult.is_blocked(game, "off") is False


def test_the_reason_says_what_matched():
    assert adult.block_reason(raw("adults-only"), "explicit") == "classificação adults-only"
    assert adult.block_reason(raw(None, "singleplayer", "nsfw"), "explicit") == "tag nsfw"
    assert adult.block_reason(raw("everyone"), "explicit") is None


def test_a_tag_without_slug_is_matched_by_its_name():
    game = {"id": 1, "tags": [{"name": "Sexual Content"}, {"name": "NSFW"}]}
    assert adult.is_blocked(game, "explicit") is True  # NSFW
    assert adult.is_blocked({"id": 1, "tags": [{"name": "Sexual Content"}]}, "mature") is True
    assert adult.is_blocked({"id": 1, "tags": [{"name": "Sexual Content"}]}, "explicit") is False


@pytest.mark.parametrize(
    "junk",
    [None, [], "texto", 42, {}, {"esrb_rating": "adults-only"}, {"esrb_rating": 5}, {"tags": "nsfw"}, {"tags": [None, 3, "nsfw"]}],
)
def test_odd_data_from_the_rawg_never_crashes_the_filter(junk):
    assert adult.block_reason(junk, "mature") is None  # nada reconhecível: não esconde, e não quebra


@pytest.mark.parametrize(
    "value, expected",
    [("explicit", "explicit"), ("mature", "mature"), ("off", "off"), (" MATURE ", "mature"), ("Off", "off"),
     (None, "explicit"), ("", "explicit"), ("desligado", "explicit"), (False, "explicit"), (0, "explicit")],
)
def test_an_unknown_level_never_turns_the_filter_off(value, expected):
    assert adult.normalize_level(value) == expected
    if expected == "explicit" and value not in ("explicit",):
        assert adult.is_blocked(raw("adults-only"), value) is True


def test_the_level_comes_from_the_environment_and_defaults_to_explicit(monkeypatch):
    monkeypatch.delenv("ADULT_CONTENT_FILTER", raising=False)
    assert build_config()["ADULT_CONTENT_FILTER"] == "explicit"
    monkeypatch.setenv("ADULT_CONTENT_FILTER", "MATURE")
    assert build_config()["ADULT_CONTENT_FILTER"] == "mature"
    monkeypatch.setenv("ADULT_CONTENT_FILTER", "off")
    assert build_config()["ADULT_CONTENT_FILTER"] == "off"
    monkeypatch.setenv("ADULT_CONTENT_FILTER", "talvez")
    assert build_config()["ADULT_CONTENT_FILTER"] == "explicit"


def test_health_shows_the_level_in_use(app, api):
    assert api.get("/api/health").get_json()["adult_content_filter"] == "explicit"
    use_level(app, "mature")
    assert api.get("/api/health").get_json()["adult_content_filter"] == "mature"


# --------------------------------------------------------------- listas, busca e catálogo
def test_the_fakes_really_are_adult_in_the_format_the_filter_reads():
    assert fake_rawg.by_name("Jardim Proibido")["esrb_rating"]["slug"] == "adults-only"
    assert fake_rawg.by_name("Noite Sem Censura")["esrb_rating"] is None
    assert "nsfw" in {t["slug"] for t in fake_rawg.by_name("Noite Sem Censura")["tags"]}
    listing = fake_rawg.fetch_json("games", {"search": "jardim"})["results"][0]
    assert "esrb_rating" in listing and "tags" in listing  # a RAWG manda os dois já na lista


@pytest.mark.parametrize("term", ["jardim", "noite sem", "quarto dezoito"])
def test_a_search_never_returns_adult_games(api, term):
    body = api.get(f"/api/games?q={term}").get_json()
    assert body["results"] == []
    assert body["count"] == 0  # nem "1 jogo" acima de uma lista vazia
    assert api.get(f"/api/search?q={term}").get_json()["games"]["items"] == []


def test_walking_the_whole_catalog_never_shows_an_adult_game(api):
    seen: set[int] = set()
    for page in (1, 2, 3):
        seen |= {game["rawg_id"] for game in api.get(f"/api/games?per_page=20&page={page}").get_json()["results"]}
    assert seen and seen.isdisjoint(ADULT)
    assert len(seen) == len(fake_rawg.GAMES) - len(ADULT)  # e todo o resto continua lá


def test_filters_of_the_catalog_do_not_bring_them_back(api):
    for genre in ("adventure", "simulation", "puzzle", "casual"):
        found = {game["rawg_id"] for game in api.get(f"/api/games?genre={genre}&per_page=40").get_json()["results"]}
        assert found.isdisjoint(ADULT), genre


def test_the_total_discounts_the_hidden_games_of_the_page(api):
    # as três páginas de 40: os escondidos (os menos populares) caem na segunda página
    second = api.get("/api/games?per_page=40&page=2").get_json()
    assert len(second["results"]) == len(fake_rawg.GAMES) - 40 - len(ADULT)
    assert second["count"] == len(fake_rawg.GAMES) - len(ADULT)


def test_featured_lists_go_through_the_same_filter(app, api):
    use_level(app, "off")
    open_lists = api.get("/api/games/featured").get_json()
    use_level(app, "explicit")
    filtered = api.get("/api/games/featured").get_json()
    for kind in ("popular", "new"):
        assert {g["rawg_id"] for g in filtered[kind]}.isdisjoint(ADULT)
        assert {g["rawg_id"] for g in filtered[kind]} <= {g["rawg_id"] for g in open_lists[kind]}


# --------------------------------------------------------------------- a página do jogo
@pytest.mark.parametrize("rawg_id", ADULT)
def test_the_page_of_an_adult_game_is_unavailable(api, rawg_id):
    response = api.get(f"/api/games/{rawg_id}")
    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "game_blocked"
    assert "conteúdo adulto" in error["message"]
    assert api.get(f"/api/games/{rawg_id}/related").status_code == 404


def test_a_game_that_does_not_exist_is_still_not_found_rather_than_blocked(api):
    assert api.get("/api/games/123").get_json()["error"]["code"] == "game_not_found"


def test_a_common_17_plus_game_stays_at_the_default_level(api):
    # The Witcher 3: ESRB Mature e tags de nudez. Só o nível "mature" o esconde.
    assert api.get(f"/api/games/{WITCHER}").status_code == 200
    assert "The Witcher 3: Wild Hunt" in names(api.get("/api/games?q=witcher"))


def test_the_blocked_answer_is_cached_so_repeating_the_address_does_not_spend_the_quota(app, api, monkeypatch):
    calls: list[str] = []

    def counting(path, params=None):
        calls.append(path)
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", counting)
    for _ in range(3):
        assert api.get(f"/api/games/{ONLY_TAG}").status_code == 404
    assert calls == [f"games/{ONLY_TAG}"]  # uma única consulta, e nenhuma de capturas de tela
    with app.app_context():
        assert rawg.cached_game(ONLY_TAG) is None  # a prévia de links também não a enxerga


# ----------------------------------------------------------- não dá para guardar um jogo 18+
@pytest.mark.parametrize("rawg_id", ADULT)
def test_an_adult_game_cannot_be_added_to_the_diary_a_review_or_a_list(app, ana, rawg_id):
    assert ana.put(f"/api/library/{rawg_id}", {"status": "quero_jogar"}).status_code == 404
    review = ana.post(f"/api/games/{rawg_id}/reviews", {"rating": 8})
    assert review.status_code == 404 and review.get_json()["error"]["code"] == "game_blocked"
    lst = ana.post("/api/lists", {"title": "Minha lista"}).get_json()["list"]
    response = ana.post(f"/api/lists/{lst['id']}/games", {"rawg_id": rawg_id})
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "game_blocked"
    with app.app_context():
        assert games_service.get_local_game(rawg_id) is None  # nem a cópia local foi criada


def test_an_adult_game_saved_before_the_filter_is_no_longer_served(app, ana):
    use_level(app, "off")
    assert ana.put(f"/api/library/{ONLY_ESRB}", {"status": "quero_jogar"}).status_code == 201
    assert ana.get(f"/api/games/{ONLY_ESRB}").status_code == 200
    use_level(app, "explicit")
    # a cópia local existe, mas a página não a serve como se a RAWG tivesse falhado
    response = ana.get(f"/api/games/{ONLY_ESRB}")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "game_blocked"


# ---------------------------------------------------------------------- os outros níveis
def test_off_shows_everything(app, api, ana):
    use_level(app, "off")
    assert names(api.get("/api/games?q=jardim")) == ["Jardim Proibido"]
    assert [g["name"] for g in api.get("/api/search?q=noite sem").get_json()["games"]["items"]] == ["Noite Sem Censura"]
    for rawg_id in ADULT:
        assert api.get(f"/api/games/{rawg_id}").status_code == 200
    assert ana.put(f"/api/library/{ONLY_TAG}", {"status": "quero_jogar"}).status_code == 201


def test_mature_also_hides_17_plus_and_suggestive_tags(app, api, ana):
    use_level(app, "mature")
    assert api.get(f"/api/games/{WITCHER}").get_json()["error"]["code"] == "game_blocked"
    assert names(api.get("/api/games?q=witcher")) == []
    assert api.get(f"/api/games/{fake_rawg.by_name('Elden Ring')['id']}").status_code == 404  # ESRB Mature
    for rawg_id in ADULT:
        assert api.get(f"/api/games/{rawg_id}").status_code == 404
    # o que não é 17+ segue normal
    assert api.get(f"/api/games/{HADES}").status_code == 200  # Teen
    assert api.get(f"/api/games/{CELESTE}").status_code == 200  # Everyone 10+
    assert ana.put(f"/api/library/{CELESTE}", {"status": "quero_jogar"}).status_code == 201


def test_an_unknown_level_behaves_like_the_default(app, api):
    use_level(app, "talvez")
    assert api.get(f"/api/games/{ONLY_ESRB}").status_code == 404
    assert api.get(f"/api/games/{WITCHER}").status_code == 200


def test_a_listing_with_no_tags_or_rating_at_all_still_works(app, api, monkeypatch):
    """A RAWG omitir `esrb_rating` e `tags` (acontece) não derruba nem esconde o jogo."""

    def bare(path, params=None):
        data = fake_rawg.fetch_json(path, params)
        for item in data.get("results", []) if isinstance(data, dict) else []:
            item.pop("esrb_rating", None)
            item.pop("tags", None)
        return data

    monkeypatch.setattr(rawg, "fetch_json", bare)
    rawg.clear_cache()
    assert "Hades" in names(api.get("/api/games?q=hades"))
