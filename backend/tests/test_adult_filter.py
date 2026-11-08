"""Filtro de conteúdo adulto: o IGDB lista jogos 18+ e o DiscPlayer os esconde (ADULT_CONTENT_FILTER)."""
from __future__ import annotations

import pytest

from app.config import build_config
from app.services import adult, games as games_service, igdb

from . import fake_igdb
from .conftest import CELESTE, HADES

ONLY_RATING = fake_igdb.by_name("Jardim Proibido")["id"]  # ESRB Adults Only, sem tema explícito
ONLY_THEME = fake_igdb.by_name("Noite Sem Censura")["id"]  # sem classificação, tema "Erotic"
THEME_AND_FANTASY = fake_igdb.by_name("Quarto Dezoito")["id"]  # sem classificação, temas "Erotic" e "Fantasy"
ADULT = [ONLY_RATING, ONLY_THEME, THEME_AND_FANTASY]
WITCHER = fake_igdb.by_name("The Witcher 3: Wild Hunt")["id"]  # ESRB Mature, PEGI 18 e ClassInd 18
ELDEN_RING = fake_igdb.by_name("Elden Ring")["id"]  # ESRB Mature


def use_level(app, level):
    """Muda o nível do filtro em tempo de execução (o cache guarda o que foi decidido antes)."""
    app.config["ADULT_CONTENT_FILTER"] = level
    igdb.clear_cache()


def names(response):
    return [game["name"] for game in response.get_json()["results"]]


def raw(*ratings, themes=()):
    """Um jogo no formato bruto do IGDB, com classificações (organização, nota) e temas (slugs)."""
    return {
        "id": 1,
        "age_ratings": [{"organization": {"name": org}, "rating_category": {"rating": rating}} for org, rating in ratings],
        "themes": [{"slug": slug, "name": slug.title()} for slug in themes],
    }


# ------------------------------------------------------------------------------ a decisão
@pytest.mark.parametrize(
    "game, explicit, mature",
    [
        (raw(("ESRB", "AO")), True, True),
        (raw(themes=["erotic"]), True, True),
        (raw(("ESRB", "T"), themes=["action", "erotic"]), True, True),
        (raw(("ESRB", "M")), False, True),  # 17+ não é 18+: só o nível mais rígido
        (raw(("PEGI", "18")), False, True),
        (raw(("USK", "18")), False, True),
        (raw(("ClassInd", "18")), False, True),
        (raw(("CLASS_IND", "18")), False, True),  # assim o IGDB escreve a classificação do Brasil
        (raw(("Class Ind", "18")), False, True),
        (raw(("GRAC", "19+")), False, True),  # na Coreia o adulto é 19+
        (raw(("CERO", "Z")), False, True),
        (raw(("GRAC", "18+")), False, True),
        (raw(("ACB", "R 18+")), False, True),
        (raw(("ACB", "RC")), False, True),
        (raw(("ESRB", "T"), ("PEGI", "16"), ("ClassInd", "16"), themes=["horror"]), False, False),
        (raw(("ESRB", "E10+"), ("ClassInd", "10")), False, False),
        (raw(("ClassInd", "L")), False, False),
        (raw(themes=["fantasy", "action"]), False, False),
        (raw(), False, False),
    ],
)
def test_each_level_hides_what_it_promises(game, explicit, mature):
    assert adult.is_blocked(game, "explicit") is explicit
    assert adult.is_blocked(game, "mature") is mature
    assert adult.is_blocked(game, "off") is False


@pytest.mark.parametrize(
    "organization, rating",
    [("ESRB", "18"), ("PEGI", "M"), ("PEGI", "AO"), ("ClassInd", "M"), ("USK", "AO"), ("Organização Nova", "18"), ("Organização Nova", "AO")],
)
def test_a_rating_only_counts_in_the_organization_that_uses_it(organization, rating):
    """"18" quer dizer coisas diferentes em cada país: o filtro olha sempre o par organização + nota."""
    assert adult.is_blocked(raw((organization, rating)), "mature") is False


def test_organization_and_rating_names_are_matched_without_regard_to_case_or_spaces():
    assert adult.is_blocked(raw((" esrb ", " ao ")), "explicit") is True
    assert adult.is_blocked(raw(("pegi", "18")), "mature") is True


def test_organization_names_are_written_the_way_the_igdb_writes_them_and_shown_in_full():
    assert adult.age_ratings(raw(("CLASS_IND", "14"), ("esrb", "T"), ("Organização Nova", "X"))) == [
        ("ClassInd", "14"), ("ESRB", "T"), ("Organização Nova", "X"),
    ]
    assert adult.block_reason(raw(("CLASS_IND", "18")), "mature") == "classificação ClassInd 18"


def test_the_reason_says_what_matched():
    assert adult.block_reason(raw(("ESRB", "AO")), "explicit") == "classificação ESRB AO"
    assert adult.block_reason(raw(("ESRB", "T"), themes=["action", "erotic"]), "explicit") == "tema erotic"
    assert adult.block_reason(raw(("ClassInd", "18")), "mature") == "classificação ClassInd 18"
    assert adult.block_reason(raw(("ClassInd", "18")), "explicit") is None
    assert adult.block_reason(raw(("ESRB", "E")), "explicit") is None


def test_a_theme_without_slug_is_matched_by_its_name():
    assert adult.is_blocked({"id": 1, "themes": [{"name": "Erotic"}]}, "explicit") is True
    assert adult.is_blocked({"id": 1, "themes": [{"name": "Action"}]}, "mature") is False


def test_the_old_format_of_the_igdb_is_still_understood():
    """O IGDB está trocando os campos de classificação: os números antigos continuam valendo."""
    legacy_ao = {"id": 1, "age_ratings": [{"category": 1, "rating": 12}]}  # ESRB, Adults Only
    legacy_classind_18 = {"id": 1, "age_ratings": [{"category": 6, "rating": 32}]}
    legacy_teen = {"id": 1, "age_ratings": [{"category": 1, "rating": 10}, {"category": 2, "rating": 4}]}
    assert adult.is_blocked(legacy_ao, "explicit") is True
    assert adult.is_blocked(legacy_classind_18, "explicit") is False and adult.is_blocked(legacy_classind_18, "mature") is True
    assert adult.is_blocked(legacy_teen, "mature") is False


@pytest.mark.parametrize(
    "junk",
    [
        None, [], "texto", 42, {}, {"age_ratings": "AO"}, {"age_ratings": 5}, {"age_ratings": [None, 3, "AO", []]},
        {"age_ratings": [{"organization": "ESRB"}, {"rating_category": {"rating": "AO"}}, {"organization": {}, "rating_category": {}}]},
        {"age_ratings": [{"category": 99, "rating": 99}, {"category": True, "rating": True}]},
        {"themes": "erotic"}, {"themes": [None, 3, "erotic", {}]}, {"themes": [{"slug": 5}]},
    ],
)
def test_odd_data_from_the_igdb_never_crashes_the_filter(junk):
    assert adult.block_reason(junk, "mature") is None  # nada reconhecível: não esconde, e não quebra


@pytest.mark.parametrize(
    "value, expected",
    [("explicit", "explicit"), ("mature", "mature"), ("off", "off"), (" MATURE ", "mature"), ("Off", "off"),
     (None, "explicit"), ("", "explicit"), ("desligado", "explicit"), (False, "explicit"), (0, "explicit")],
)
def test_an_unknown_level_never_turns_the_filter_off(value, expected):
    assert adult.normalize_level(value) == expected
    if expected == "explicit" and value not in ("explicit",):
        assert adult.is_blocked(raw(("ESRB", "AO")), value) is True


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
    rated = fake_igdb.by_name("Jardim Proibido")
    assert adult.age_ratings(rated) == [("ESRB", "AO")]
    assert adult.age_ratings(fake_igdb.by_name("Noite Sem Censura")) == []
    assert "erotic" in {t["slug"] for t in fake_igdb.by_name("Noite Sem Censura")["themes"]}
    assert adult.age_ratings(fake_igdb.by_name("The Witcher 3: Wild Hunt")) == [("ESRB", "M"), ("ClassInd", "18"), ("PEGI", "18")]
    # o IGDB manda as duas coisas já na lista, desde que o back-end as peça
    # (como o IGDB, o simulado omite o campo que está vazio)
    by_rating = fake_igdb.fetch_json(igdb.Query("games", igdb._SUMMARY_FIELDS, search="jardim", limit=5))[0]
    by_theme = fake_igdb.fetch_json(igdb.Query("games", igdb._SUMMARY_FIELDS, search="noite sem", limit=5))[0]
    assert "age_ratings" in by_rating and "themes" in by_theme
    assert "age_ratings.organization.name" in igdb._SUMMARY_FIELDS and "themes.slug" in igdb._SUMMARY_FIELDS


@pytest.mark.parametrize("term", ["jardim", "noite sem", "quarto dezoito"])
def test_a_search_never_returns_adult_games(api, term):
    body = api.get(f"/api/games?q={term}").get_json()
    assert body["results"] == []
    assert body["count"] == 0  # nem "1 jogo" acima de uma lista vazia
    assert api.get(f"/api/search?q={term}").get_json()["games"]["items"] == []


@pytest.mark.parametrize("ordering", ["name", "released", "popular"])
def test_a_search_with_its_own_order_never_returns_them_either(api, ordering):
    assert api.get(f"/api/games?q=jardim&ordering={ordering}").get_json()["results"] == []


def test_walking_the_whole_catalog_never_shows_an_adult_game(api):
    seen: set[int] = set()
    for page in (1, 2, 3):
        seen |= {game["igdb_id"] for game in api.get(f"/api/games?per_page=20&page={page}").get_json()["results"]}
    assert seen and seen.isdisjoint(ADULT)
    assert len(seen) == len(fake_igdb.MAIN_GAMES) - len(ADULT)  # e todo o resto continua lá


def test_filters_of_the_catalog_do_not_bring_them_back(api):
    for genre in ("adventure", "simulator", "puzzle", "card-and-board-game", "indie"):
        found = {game["igdb_id"] for game in api.get(f"/api/games?genre={genre}&per_page=40").get_json()["results"]}
        assert found.isdisjoint(ADULT), genre
    for ordering in ("released", "name", "rating", "critics"):
        found = {game["igdb_id"] for game in api.get(f"/api/games?ordering={ordering}&per_page=40").get_json()["results"]}
        assert found.isdisjoint(ADULT), ordering


def test_the_total_discounts_the_hidden_games_of_the_page(api):
    # as duas páginas de 40: os escondidos (os menos populares) caem na segunda página
    second = api.get("/api/games?per_page=40&page=2").get_json()
    assert len(second["results"]) == len(fake_igdb.MAIN_GAMES) - 40 - len(ADULT)
    assert second["count"] == len(fake_igdb.MAIN_GAMES) - len(ADULT)


def test_featured_lists_go_through_the_same_filter(app, api):
    use_level(app, "off")
    open_lists = api.get("/api/games/featured").get_json()
    use_level(app, "explicit")
    filtered = api.get("/api/games/featured").get_json()
    for kind in ("popular", "new"):
        assert {g["igdb_id"] for g in filtered[kind]}.isdisjoint(ADULT)
        assert {g["igdb_id"] for g in filtered[kind]} <= {g["igdb_id"] for g in open_lists[kind]}
    assert filtered["popular"] and filtered["new"]


# --------------------------------------------------------------------- a página do jogo
@pytest.mark.parametrize("igdb_id", ADULT)
def test_the_page_of_an_adult_game_is_unavailable(api, igdb_id):
    response = api.get(f"/api/games/{igdb_id}")
    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "game_blocked"
    assert "conteúdo adulto" in error["message"]
    assert api.get(f"/api/games/{igdb_id}/related").status_code == 404


def test_a_game_that_does_not_exist_is_still_not_found_rather_than_blocked(api):
    assert api.get("/api/games/123").get_json()["error"]["code"] == "game_not_found"


def test_a_common_17_plus_game_stays_at_the_default_level(api):
    # The Witcher 3: ESRB Mature e ClassInd 18. Só o nível "mature" o esconde.
    assert api.get(f"/api/games/{WITCHER}").status_code == 200
    assert "The Witcher 3: Wild Hunt" in names(api.get("/api/games?q=witcher"))


def test_the_blocked_answer_is_cached_so_repeating_the_address_does_not_spend_the_quota(app, api, monkeypatch):
    calls: list[igdb.Query] = []

    def counting(query):
        calls.append(query)
        return fake_igdb.fetch_json(query)

    monkeypatch.setattr(igdb, "fetch_json", counting)
    for _ in range(3):
        assert api.get(f"/api/games/{ONLY_THEME}").status_code == 404
    assert len(calls) == 1  # uma única consulta ao IGDB para as três visitas
    assert calls[0].filters == (("id", "=", ONLY_THEME),)
    with app.app_context():
        assert igdb.cached_game(ONLY_THEME) is None  # a prévia de links também não a enxerga


# ----------------------------------------------------------- não dá para guardar um jogo 18+
@pytest.mark.parametrize("igdb_id", ADULT)
def test_an_adult_game_cannot_be_added_to_the_diary_a_review_or_a_list(app, ana, igdb_id):
    assert ana.put(f"/api/library/{igdb_id}", {"status": "quero_jogar"}).status_code == 404
    review = ana.post(f"/api/games/{igdb_id}/reviews", {"rating": 8})
    assert review.status_code == 404 and review.get_json()["error"]["code"] == "game_blocked"
    lst = ana.post("/api/lists", {"title": "Minha lista"}).get_json()["list"]
    response = ana.post(f"/api/lists/{lst['id']}/games", {"igdb_id": igdb_id})
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "game_blocked"
    with app.app_context():
        assert games_service.get_local_game(igdb_id) is None  # nem a cópia local foi criada


def test_an_adult_game_saved_before_the_filter_is_no_longer_served(app, ana):
    use_level(app, "off")
    assert ana.put(f"/api/library/{ONLY_RATING}", {"status": "quero_jogar"}).status_code == 201
    assert ana.get(f"/api/games/{ONLY_RATING}").status_code == 200
    use_level(app, "explicit")
    # a cópia local existe, mas a página não a serve como se o IGDB tivesse falhado
    response = ana.get(f"/api/games/{ONLY_RATING}")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "game_blocked"


# ---------------------------------------------------------------------- os outros níveis
def test_off_shows_everything(app, api, ana):
    use_level(app, "off")
    assert names(api.get("/api/games?q=jardim")) == ["Jardim Proibido"]
    assert [g["name"] for g in api.get("/api/search?q=noite sem").get_json()["games"]["items"]] == ["Noite Sem Censura"]
    for igdb_id in ADULT:
        assert api.get(f"/api/games/{igdb_id}").status_code == 200
    assert ana.put(f"/api/library/{ONLY_THEME}", {"status": "quero_jogar"}).status_code == 201


def test_mature_also_hides_17_plus_games(app, api, ana):
    use_level(app, "mature")
    assert api.get(f"/api/games/{WITCHER}").get_json()["error"]["code"] == "game_blocked"
    assert names(api.get("/api/games?q=witcher")) == []
    assert api.get(f"/api/games/{ELDEN_RING}").status_code == 404  # ESRB Mature
    for igdb_id in ADULT:
        assert api.get(f"/api/games/{igdb_id}").status_code == 404
    # o que não é 17+ segue normal
    assert api.get(f"/api/games/{HADES}").status_code == 200  # ESRB Teen, ClassInd 14
    assert api.get(f"/api/games/{CELESTE}").status_code == 200  # ESRB Everyone 10+
    assert ana.put(f"/api/library/{CELESTE}", {"status": "quero_jogar"}).status_code == 201


def test_mature_removes_the_17_plus_games_from_the_whole_catalog(app, api):
    use_level(app, "mature")
    seen: set[int] = set()
    for page in (1, 2, 3):
        seen |= {game["igdb_id"] for game in api.get(f"/api/games?per_page=20&page={page}").get_json()["results"]}
    hidden = {g["id"] for g in fake_igdb.MAIN_GAMES if adult.is_blocked(g, "mature")}
    assert hidden > set(ADULT) and WITCHER in hidden and ELDEN_RING in hidden
    assert seen and seen.isdisjoint(hidden)
    assert len(seen) == len(fake_igdb.MAIN_GAMES) - len(hidden)


def test_an_unknown_level_behaves_like_the_default(app, api):
    use_level(app, "talvez")
    assert api.get(f"/api/games/{ONLY_RATING}").status_code == 404
    assert api.get(f"/api/games/{WITCHER}").status_code == 200


def test_a_listing_with_no_ratings_or_themes_at_all_still_works(app, api, monkeypatch):
    """O IGDB omitir `age_ratings` e `themes` (acontece: ele não manda campo vazio) não derruba nem esconde o jogo."""

    def bare(query):
        data = fake_igdb.fetch_json(query)
        for item in data if isinstance(data, list) else ():
            item.pop("age_ratings", None)
            item.pop("themes", None)
        return data

    monkeypatch.setattr(igdb, "fetch_json", bare)
    igdb.clear_cache()
    assert "Hades" in names(api.get("/api/games?q=hades"))
