"""Integração com o IGDB: login da Twitch, consultas, erros, cache, normalização e rotas do catálogo."""
from __future__ import annotations

import logging
from datetime import date

import pytest
import requests

from app.services import adult, igdb
from app.services.igdb import Query, to_apicalypse

from . import fake_igdb
from .conftest import HADES
from .fake_igdb_server import parse_apicalypse


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, text_json=True):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self._text_json = text_json
        self.text = "corpo"

    def json(self):
        if not self._text_json:
            raise ValueError("não é JSON")
        return self._payload


def token_response(value="tok-1"):
    return FakeResponse(payload={"access_token": value, "expires_in": 5_000_000, "token_type": "bearer"})


@pytest.fixture
def real_transport(app, monkeypatch):
    """Usa o fetch_json de verdade, com a camada HTTP (o IGDB e o login da Twitch) substituída."""
    monkeypatch.undo()  # remove o patch do conftest em fetch_json
    igdb.clear_cache()
    igdb.clear_token()
    calls: list[dict] = []
    outcome: dict = {"token": token_response(), "response": FakeResponse(payload=[])}

    def fake_post(url, params=None, data=None, headers=None, timeout=None):
        calls.append({"url": url, "params": dict(params or {}), "data": data, "headers": headers, "timeout": timeout})
        result = outcome["token" if "oauth2/token" in url else "response"]
        if isinstance(result, list):  # uma sequência de respostas, uma por chamada
            result = result.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(igdb._session, "post", fake_post)
    yield calls, outcome
    igdb.clear_token()


GAME_QUERY = Query("games", ("name",), (("id", "=", 1),), limit=1)


def api_calls(calls):
    return [c for c in calls if "oauth2/token" not in c["url"]]


def token_calls(calls):
    return [c for c in calls if "oauth2/token" in c["url"]]


# ---------------------------------------------------------------- transporte e erros
def test_request_sends_credentials_server_side_with_a_timeout(app, real_transport):
    calls, outcome = real_transport
    outcome["response"] = FakeResponse(payload=[{"id": 1}])
    with app.app_context():
        assert igdb.fetch_json(GAME_QUERY) == [{"id": 1}]
    token, sent = calls
    assert token["url"] == "https://id.twitch.tv/oauth2/token"
    assert token["data"] == {"client_id": "id-de-teste", "client_secret": "segredo-de-teste", "grant_type": "client_credentials"}
    assert token["params"] == {}  # o segredo vai no corpo, nunca na URL
    assert sent["url"] == "https://api.igdb.com/v4/games"
    assert sent["headers"]["Client-ID"] == "id-de-teste" and sent["headers"]["Authorization"] == "Bearer tok-1"
    assert sent["data"] == b"fields name; where id = 1; limit 1; offset 0;"
    assert sent["timeout"] and all(t > 0 for t in sent["timeout"])


def test_the_count_endpoint_is_used_for_totals(app, real_transport):
    calls, outcome = real_transport
    outcome["response"] = FakeResponse(payload={"count": 12})
    with app.app_context():
        assert igdb.fetch_json(Query("games", filters=(("cover", "notnull", None),), count=True)) == {"count": 12}
    assert api_calls(calls)[0]["url"] == "https://api.igdb.com/v4/games/count"
    assert api_calls(calls)[0]["data"] == b"where cover != null;"


@pytest.mark.parametrize(
    "response, error_type, status, code",
    [
        (FakeResponse(403), igdb.IgdbNotConfigured, 503, "igdb_not_configured"),
        (FakeResponse(429, headers={"Retry-After": "30"}), igdb.IgdbRateLimited, 429, "igdb_rate_limited"),
        (FakeResponse(400), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
        (FakeResponse(500), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
        (FakeResponse(502), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
        (FakeResponse(200, text_json=False), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
        (requests.Timeout("lento"), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
        (requests.ConnectionError("sem rede"), igdb.IgdbUnavailable, 503, "igdb_unavailable"),
    ],
)
def test_http_failures_become_specific_errors(app, real_transport, response, error_type, status, code):
    _, outcome = real_transport
    outcome["response"] = response
    with app.app_context(), pytest.raises(error_type) as caught:
        igdb.fetch_json(GAME_QUERY)
    assert caught.value.status == status and caught.value.code == code


def test_rate_limit_error_carries_retry_after(app, real_transport):
    _, outcome = real_transport
    outcome["response"] = FakeResponse(429, headers={"Retry-After": "42"})
    with app.app_context(), pytest.raises(igdb.IgdbRateLimited) as caught:
        igdb.fetch_json(GAME_QUERY)
    assert caught.value.retry_after == 42


def test_the_token_is_reused_and_renewed_only_when_it_is_about_to_expire(app, real_transport):
    calls, outcome = real_transport
    outcome["response"] = FakeResponse(payload=[])
    with app.app_context():
        igdb.fetch_json(GAME_QUERY)
        igdb.fetch_json(GAME_QUERY)
        assert len(token_calls(calls)) == 1  # uma só ida à Twitch para duas consultas
        igdb._token["expires_at"] = 0.0  # venceu
        outcome["token"] = token_response("tok-2")
        igdb.fetch_json(GAME_QUERY)
    assert len(token_calls(calls)) == 2
    assert [c["headers"]["Authorization"] for c in api_calls(calls)] == ["Bearer tok-1", "Bearer tok-1", "Bearer tok-2"]


def test_a_revoked_token_is_renewed_and_the_request_repeated_once(app, real_transport):
    calls, outcome = real_transport
    outcome["token"] = [token_response("tok-1"), token_response("tok-2")]
    outcome["response"] = [FakeResponse(401), FakeResponse(payload=[{"id": 1}])]
    with app.app_context():
        assert igdb.fetch_json(GAME_QUERY) == [{"id": 1}]
    assert [c["headers"]["Authorization"] for c in api_calls(calls)] == ["Bearer tok-1", "Bearer tok-2"]
    assert len(token_calls(calls)) == 2


def test_a_second_refusal_means_the_credentials_are_wrong(app, real_transport):
    calls, outcome = real_transport
    outcome["token"] = [token_response("tok-1"), token_response("tok-2")]
    outcome["response"] = [FakeResponse(401), FakeResponse(401)]
    with app.app_context(), pytest.raises(igdb.IgdbNotConfigured):
        igdb.fetch_json(GAME_QUERY)
    assert len(api_calls(calls)) == 2  # tenta de novo uma vez, e só uma


@pytest.mark.parametrize(
    "response, error_type",
    [
        (FakeResponse(400), igdb.IgdbNotConfigured),
        (FakeResponse(401), igdb.IgdbNotConfigured),
        (FakeResponse(403), igdb.IgdbNotConfigured),
        (FakeResponse(500), igdb.IgdbUnavailable),
        (FakeResponse(200, text_json=False), igdb.IgdbUnavailable),
        (FakeResponse(200, payload={"sem": "token"}), igdb.IgdbUnavailable),
        (requests.Timeout("lento"), igdb.IgdbUnavailable),
        (requests.ConnectionError("sem rede"), igdb.IgdbUnavailable),
    ],
)
def test_failures_of_the_twitch_login_are_translated(app, real_transport, response, error_type):
    calls, outcome = real_transport
    outcome["token"] = response
    with app.app_context(), pytest.raises(error_type):
        igdb.fetch_json(GAME_QUERY)
    assert api_calls(calls) == []  # sem token, nem tenta consultar o IGDB


def test_missing_credentials_fail_before_any_network_call(app, real_transport):
    calls, _ = real_transport
    for missing in ("IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET"):
        with app.app_context():
            original = app.config[missing]
            app.config[missing] = ""
            try:
                with pytest.raises(igdb.IgdbNotConfigured):
                    igdb.fetch_json(GAME_QUERY)
            finally:
                app.config[missing] = original
    assert calls == []


def test_routes_translate_igdb_errors_into_clean_json(api, real_transport):
    _, outcome = real_transport
    outcome["response"] = FakeResponse(429, headers={"Retry-After": "12"})
    response = api.get("/api/games?q=zelda")
    assert response.status_code == 429 and response.headers["Retry-After"] == "12"
    assert response.get_json()["error"]["code"] == "igdb_rate_limited"
    outcome["response"] = FakeResponse(500)
    igdb.clear_cache()
    response = api.get("/api/games?q=zelda")
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "igdb_unavailable"


def test_credentials_never_leak_in_logs_or_responses(app, api, real_transport, caplog):
    _, outcome = real_transport
    secret_url = "https://id.twitch.tv/oauth2/token?client_secret=segredo-de-teste&client_id=id-de-teste"
    for target in ("response", "token"):
        igdb.clear_token()
        igdb.clear_cache()
        outcome["response"] = FakeResponse(payload=[])
        outcome["token"] = token_response()
        outcome[target] = requests.ConnectionError(f"falha em {secret_url}")
        with caplog.at_level(logging.DEBUG):
            response = api.get("/api/games?q=zelda")
        assert response.status_code == 503
        body = response.get_data(as_text=True)
        assert "segredo-de-teste" not in body and "id-de-teste" not in body
        assert "segredo-de-teste" not in caplog.text


def test_calls_are_spaced_to_respect_the_four_per_second_limit(app, real_transport, monkeypatch):
    app.config["IGDB_MIN_INTERVAL"] = 0.26
    igdb._next_slot = 0.0
    sleeps: list[float] = []
    monkeypatch.setattr(igdb.time, "sleep", sleeps.append)
    with app.app_context():
        for _ in range(3):
            igdb.fetch_json(GAME_QUERY)
    # a primeira vai direto; as outras reservam vagas seguidas, 0,26 s uma depois da outra
    assert len(sleeps) == 2
    assert sleeps[0] == pytest.approx(0.26, abs=0.05) and sleeps[1] == pytest.approx(0.52, abs=0.05)


def test_health_reports_whether_igdb_is_configured_without_revealing_the_credentials(app, api):
    body = api.get("/api/health").get_json()
    assert body["igdb_configured"] is True
    assert "id-de-teste" not in str(body) and "segredo-de-teste" not in str(body)
    app.config["IGDB_CLIENT_SECRET"] = ""
    assert api.get("/api/health").get_json()["igdb_configured"] is False


# ------------------------------------------------------------- a consulta (Apicalypse)
def test_a_query_is_written_as_apicalypse_text():
    query = Query(
        "games",
        ("name", "cover.image_id"),
        (("genres", "in", (4, 5)), ("first_release_date", ">=", 100), ("parent_game", "null", None), ("cover", "notnull", None)),
        search="zelda",
        sort="name asc",
        limit=24,
        offset=48,
    )
    assert to_apicalypse(query) == (
        'fields name,cover.image_id; where genres = (4,5) & first_release_date >= 100 & parent_game = null'
        ' & cover != null; search "zelda"; sort name asc; limit 24; offset 48;'
    )


def test_a_count_query_has_only_the_filters_and_the_search():
    query = Query("games", filters=(("id", "=", 5),), search="x", count=True)
    assert to_apicalypse(query) == 'where id = 5; search "x";'


@pytest.mark.parametrize(
    "query",
    [
        Query("games", ("name; limit 500",)),  # campo com mais do que um nome
        Query("games", ()),  # sem campos
        Query("games", ("name",), (("id", "=", "1; limit 500"),)),  # valor que não é número
        Query("games", ("name",), (("id", "=", True),)),
        Query("games", ("name",), (("id; drop", "=", 1),)),
        Query("games", ("name",), (("id", "like", 1),)),
        Query("games", ("name",), (("genres", "in", ()),)),
        Query("games", ("name",), (("genres", "in", (1, "2)")),)),
        Query("games", ("name",), sort="name; limit 1"),
        Query("games", ("name",), limit="10; offset 5"),
    ],
)
def test_a_query_with_values_that_are_not_safe_is_refused(query):
    with pytest.raises(ValueError):
        to_apicalypse(query)


def test_search_text_cannot_escape_its_quotes():
    text = to_apicalypse(Query("games", ("name",), search='x" ; where id = 1 ; \\ y'))
    assert text.count('"') == 2 and "search " in text
    assert igdb.clean_search('a "b" \\ c; d\n e') == "a b c d e"
    assert igdb.clean_search("x" * 300) == "x" * 100


def test_every_query_the_app_builds_survives_the_trip_through_the_text(app, monkeypatch):
    """O servidor de teste lê o texto com um analisador próprio: o que o app escreve tem de voltar igual."""
    seen: list[Query] = []

    def spy(query):
        seen.append(query)
        return fake_igdb.fetch_json(query)

    monkeypatch.setattr(igdb, "fetch_json", spy)
    with app.app_context():
        igdb.search_games(search="hades", page=2, page_size=5)
        igdb.search_games(genres="adventure,indie", platforms="2,7", year=2018, ordering="popular")
        igdb.search_games(ordering="released")
        igdb.search_games(ordering="rating")
        igdb.search_games(ordering="critics")
        igdb.search_games(ordering="name", page_size=40)
        igdb.search_games(search="hades", ordering="released")  # busca com ordem própria
        igdb.featured_games("popular")
        igdb.featured_games("new")
        igdb.get_game(HADES)
        igdb.list_genres()
    assert len(seen) >= 15
    for query in seen:
        endpoint = query.endpoint + ("/count" if query.count else "")
        assert parse_apicalypse(endpoint, to_apicalypse(query)) == query


# ---------------------------------------------------------------------------- cache
def test_cache_avoids_repeated_requests_and_serves_stale_data_when_igdb_fails(app, monkeypatch):
    hits = {"n": 0}

    def counting(query):
        hits["n"] += 1
        return fake_igdb.fetch_json(query)

    monkeypatch.setattr(igdb, "fetch_json", counting)
    with app.app_context():
        igdb.search_games(search="hades")
        first = hits["n"]  # a consulta e a contagem do total
        igdb.search_games(search="hades")
        assert hits["n"] == first
        igdb.search_games(search="celeste")
        assert hits["n"] == 2 * first

        # expira o cache (mas ele continua servível como cópia obsoleta) e derruba o IGDB
        app.config["IGDB_TTL_SEARCH"] = 0
        igdb.clear_cache()
        igdb.search_games(search="hades")
        before = hits["n"]

        def down(_query):
            raise igdb.IgdbUnavailable()

        monkeypatch.setattr(igdb, "fetch_json", down)
        stale = igdb.search_games(search="hades")
        assert stale["results"][0]["name"] == "Hades"
        assert hits["n"] == before


def test_failures_are_not_cached(app, monkeypatch):
    state = {"fail": True}

    def flaky(query):
        if state["fail"]:
            raise igdb.IgdbUnavailable()
        return fake_igdb.fetch_json(query)

    monkeypatch.setattr(igdb, "fetch_json", flaky)
    with app.app_context():
        with pytest.raises(igdb.IgdbUnavailable):
            igdb.search_games(search="hades")
        state["fail"] = False
        assert igdb.search_games(search="hades")["results"]


# ---------------------------------------------------------------- normalização
def test_normalization_tolerates_missing_fields():
    summary = igdb.normalize_summary({"id": 1})
    assert summary["name"] == "Sem título"
    assert summary["cover_url"] is None and summary["cover_thumb_url"] is None
    assert summary["released"] is None and summary["genres"] == [] and summary["platforms"] == []
    assert summary["critic_score"] is None
    detail = igdb.normalize_detail({"id": 1, "name": "X"})
    assert detail["description"] == "" and detail["developers"] == [] and detail["publishers"] == []
    assert detail["igdb_rating"] is None and detail["igdb_ratings_count"] == 0
    assert detail["age_rating"] is None and detail["website"] is None and detail["screenshots"] == []
    assert detail["cover_additional_url"] is None and detail["playtime"] is None


@pytest.mark.parametrize("raw", [{}, {"id": "7"}, {"id": None}, {"id": True}, {"name": "sem id"}])
def test_entries_without_a_valid_id_are_dropped(raw):
    assert igdb.normalize_summary(raw) is None


@pytest.mark.parametrize(
    "url",
    ["http://images.igdb.com/a.jpg", "javascript:alert(1)", "data:image/png;base64,AAAA", "//evil.example/a.jpg", "", None, 42, "https://" + "a" * 700],
)
def test_only_https_images_are_accepted(url):
    assert igdb.safe_image_url(url) is None


def test_cover_urls_are_built_from_the_image_id():
    summary = igdb.normalize_summary({"id": 1, "cover": {"id": 9, "image_id": "co1abc"}})
    assert summary["cover_url"] == "https://images.igdb.com/igdb/image/upload/t_720p/co1abc.jpg"
    assert summary["cover_thumb_url"] == "https://images.igdb.com/igdb/image/upload/t_cover_big/co1abc.jpg"


@pytest.mark.parametrize("image_id", ["../x", "a/b", "a b", "", None, 42, "x" * 70, "co1?x=1"])
def test_an_image_id_that_is_not_plain_never_becomes_a_url(image_id):
    assert igdb.image_url(image_id, "t_720p") is None
    assert igdb.normalize_summary({"id": 1, "cover": {"image_id": image_id}})["cover_url"] is None


def test_thumbnail_url_rewrites_igdb_covers_and_leaves_other_hosts_alone():
    big = "https://images.igdb.com/igdb/image/upload/t_720p/co1abc.jpg"
    assert igdb.thumb_url(big) == "https://images.igdb.com/igdb/image/upload/t_cover_big/co1abc.jpg"
    old = "https://media.rawg.io/media/games/aaa/bbb.jpg"  # capas de jogos guardados antes da troca de serviço
    assert igdb.thumb_url(old) == old
    assert igdb.thumb_url(None) is None and igdb.thumb_url("") is None


@pytest.mark.parametrize(
    "stamp, expected",
    [(1600000000, "2020-09-13"), (0, "1970-01-01"), (1_700_000_000.0, "2023-11-14"),
     (None, None), ("1600000000", None), (True, None), (-86400, None), (10**15, None), (float("inf"), None)],
)
def test_release_dates_come_from_the_timestamp_in_utc(stamp, expected):
    assert igdb.release_date({"first_release_date": stamp}) == expected


def test_genres_are_shown_in_portuguese_and_unknown_ones_keep_the_name_they_came_with():
    genres = [{"slug": "role-playing-rpg", "name": "Role-playing (RPG)"}, {"slug": "novo-genero", "name": "Novo"}, "x", {"slug": "x"}]
    assert igdb.normalize_summary({"id": 1, "genres": genres})["genres"] == ["RPG", "Novo"]


def test_platforms_are_grouped_in_families_in_a_fixed_order():
    raw = {"id": 1, "platforms": [{"id": 130}, {"id": 167}, {"id": 6}, {"id": 48}, {"id": 999}, 14, None, True, "6"]}
    assert igdb.normalize_summary(raw)["platforms"] == ["PC", "PlayStation", "Nintendo", "macOS"]


@pytest.mark.parametrize("critic, expected", [(87.6, 88), (100, 100), (250, 100), (0, None), (-3, None), (None, None), (True, None), ("90", None)])
def test_the_critic_score_is_a_whole_number_from_0_to_100(critic, expected):
    assert igdb.normalize_summary({"id": 1, "aggregated_rating": critic})["critic_score"] == expected


def test_the_igdb_rating_is_shown_on_a_scale_of_ten():
    detail = igdb.normalize_detail({"id": 1, "total_rating": 84.0, "total_rating_count": 321})
    assert detail["igdb_rating"] == 8.4 and detail["igdb_ratings_count"] == 321
    assert igdb.normalize_detail({"id": 1, "total_rating": 0})["igdb_rating"] is None
    assert igdb.normalize_detail({"id": 1, "total_rating_count": True})["igdb_ratings_count"] == 0


def _ratings(*pairs):
    return {"id": 1, "age_ratings": [{"organization": {"name": o}, "rating_category": {"rating": r}} for o, r in pairs]}


def test_the_age_rating_shown_prefers_the_brazilian_one():
    assert igdb.age_rating(_ratings(("ESRB", "M"), ("ClassInd", "18"), ("PEGI", "18"))) == {"label": "18 anos", "organization": "ClassInd"}
    assert igdb.age_rating(_ratings(("PEGI", "16"), ("ESRB", "T"))) == {"label": "Teen", "organization": "ESRB"}
    assert igdb.age_rating(_ratings(("PEGI", "7"))) == {"label": "PEGI 7", "organization": "PEGI"}
    assert igdb.age_rating(_ratings(("USK", "12"))) == {"label": "USK 12", "organization": "USK"}
    assert igdb.age_rating(_ratings(("ClassInd", "L"))) == {"label": "Livre", "organization": "ClassInd"}
    assert igdb.age_rating(_ratings(("ESRB", "M")))["label"] == "Mature 17+"
    assert igdb.age_rating({"id": 1}) is None


def test_the_brazilian_rating_is_recognized_with_the_name_the_igdb_really_uses():
    """O IGDB manda `CLASS_IND`, não `ClassInd`: sem esse cuidado a classificação do Brasil nunca era usada."""
    shown = igdb.age_rating(_ratings(("ESRB", "T"), ("CLASS_IND", "14")))
    assert shown == {"label": "14 anos", "organization": "ClassInd"}
    assert igdb.age_rating(_ratings(("CLASS_IND", "L"), ("PEGI", "3"))) == {"label": "Livre", "organization": "ClassInd"}


def test_age_ratings_are_read_in_the_current_and_in_the_old_format_and_junk_is_ignored():
    legacy = {"id": 1, "age_ratings": [{"category": 1, "rating": 11}, {"category": 6, "rating": 32}, {"category": 2, "rating": 5}]}
    assert adult.age_ratings(legacy) == [("ESRB", "M"), ("ClassInd", "18"), ("PEGI", "18")]
    junk = {"id": 1, "age_ratings": [None, 3, {}, {"organization": {}, "rating_category": {}}, {"organization": {"name": "ESRB"}}, {"category": 99, "rating": 1}]}
    assert adult.age_ratings(junk) == []
    assert adult.age_ratings({"age_ratings": "M"}) == [] and adult.age_ratings(None) == []


def test_the_official_site_skips_stores_and_social_networks_and_unsafe_links():
    sites = [{"url": "https://store.steampowered.com/app/1"}, {"url": "https://x.com/jogo"}, {"url": "javascript:alert(1)"},
             {"url": None}, "x", {"url": "https://www.jogo.exemplo.com/"}, {"url": "https://outro.exemplo.com"}]
    assert igdb.normalize_detail({"id": 1, "websites": sites})["website"] == "https://www.jogo.exemplo.com/"
    assert igdb.normalize_detail({"id": 1, "websites": [{"url": "https://www.youtube.com/x"}]})["website"] is None


def test_unsafe_website_urls_are_dropped():
    assert igdb.safe_web_url("javascript:alert(1)") is None
    assert igdb.safe_web_url("https://jogo.exemplo.com") == "https://jogo.exemplo.com"


def test_the_description_is_plain_text_and_falls_back_to_the_storyline():
    detail = igdb.normalize_detail({"id": 1, "summary": "Olá <b>mundo</b>\r\n\r\n\r\n\r\nFim &amp; tudo"})
    assert "<" not in detail["description"] and detail["description"] == "Olá mundo\n\nFim & tudo"
    assert igdb.normalize_detail({"id": 1, "summary": "  ", "storyline": "A história."})["description"] == "A história."
    assert len(igdb.normalize_detail({"id": 1, "summary": "x" * 9000})["description"]) == 6000


def test_developers_and_publishers_come_from_the_roles_of_each_company_without_repeats():
    companies = [
        {"developer": True, "publisher": False, "company": {"name": "Estúdio A"}},
        {"developer": True, "publisher": True, "company": {"name": "Estúdio B"}},
        {"developer": True, "publisher": False, "company": {"name": "Estúdio A"}},
        {"developer": False, "publisher": True, "company": {"name": "Editora C"}},
        {"developer": True, "company": None}, "x", None,
    ]
    detail = igdb.normalize_detail({"id": 1, "involved_companies": companies})
    assert detail["developers"] == ["Estúdio A", "Estúdio B"] and detail["publishers"] == ["Estúdio B", "Editora C"]


def test_the_page_images_come_from_artworks_and_screenshots():
    detail = igdb.normalize_detail({
        "id": 1, "artworks": [{"image_id": "ar1"}],
        "screenshots": [{"image_id": f"sc{n}"} for n in range(9)] + [{"image_id": "../x"}],
    })
    assert detail["cover_additional_url"] == "https://images.igdb.com/igdb/image/upload/t_1080p/ar1.jpg"
    assert len(detail["screenshots"]) == 6 and detail["screenshots"][0].endswith("/t_screenshot_big/sc0.jpg")
    no_art = igdb.normalize_detail({"id": 1, "screenshots": [{"image_id": "sc1"}]})
    assert no_art["cover_additional_url"].endswith("/t_1080p/sc1.jpg")  # sem arte oficial, a primeira captura


# ------------------------------------------------------------------ rotas do catálogo
def test_catalog_search_pagination_and_shape(api):
    body = api.get("/api/games?q=hollow&per_page=5").get_json()
    assert [g["name"] for g in body["results"]] == ["Hollow Knight"]
    first = api.get("/api/games?page=1&per_page=10").get_json()
    second = api.get("/api/games?page=2&per_page=10").get_json()
    assert len(first["results"]) == 10 and first["has_next"] is True and first["has_previous"] is False
    assert second["has_previous"] is True
    assert {g["igdb_id"] for g in first["results"]}.isdisjoint({g["igdb_id"] for g in second["results"]})
    game = first["results"][0]
    assert {"igdb_id", "name", "slug", "cover_url", "cover_thumb_url", "released", "genres", "platforms", "critic_score"} <= set(game)
    assert "age_ratings" not in game and "themes" not in game  # o que serve ao filtro não vai para o navegador


def test_the_catalog_lists_only_main_games_not_expansions(api):
    seen = set()
    for page in (1, 2, 3):
        seen |= {g["name"] for g in api.get(f"/api/games?per_page=20&page={page}").get_json()["results"]}
    assert "Hades" in seen and "Hades: Pacote de Teste" not in seen
    assert api.get("/api/games?q=pacote de teste").get_json()["results"] == []
    assert api.get(f"/api/games/{fake_igdb.by_name('Hades: Pacote de Teste')['id']}").status_code == 200  # a página abre


def test_catalog_filters(api):
    rpg = api.get("/api/games?genre=role-playing-rpg&per_page=40").get_json()["results"]
    assert rpg and all("RPG" in g["genres"] for g in rpg)
    nintendo = api.get("/api/games?platform=7&per_page=40").get_json()["results"]
    assert nintendo and all("Nintendo" in g["platforms"] for g in nintendo)
    both = api.get("/api/games?platform=2,3&per_page=40").get_json()["results"]
    assert both and all({"PlayStation", "Xbox"} & set(g["platforms"]) for g in both)
    in_2018 = api.get("/api/games?year=2018&per_page=40").get_json()["results"]
    assert {g["name"] for g in in_2018} >= {"Celeste", "God of War"}
    assert all(g["released"].startswith("2018") for g in in_2018)
    combined = api.get("/api/games?genre=platform&platform=7&year=2018&per_page=40").get_json()["results"]
    assert [g["name"] for g in combined] == ["Celeste"]


def test_a_genre_or_platform_the_igdb_does_not_have_is_an_empty_result(api):
    for query in ("genre=nao-existe", "platform=999", "genre=nao-existe,tambem-nao"):
        body = api.get(f"/api/games?{query}").get_json()
        assert body["results"] == [] and body["count"] == 0 and body["has_next"] is False, query


def test_catalog_orderings(api):
    released = [g["released"] for g in api.get("/api/games?ordering=released&per_page=40").get_json()["results"]]
    assert released == sorted(released, reverse=True)
    assert released[0] <= date.today().isoformat()  # os que ainda não saíram ficam de fora
    names = [g["name"] for g in api.get("/api/games?ordering=name&per_page=40").get_json()["results"]]
    assert names == sorted(names, key=str.lower)
    critics = [g["name"] for g in api.get("/api/games?ordering=critics&per_page=40").get_json()["results"]]
    assert critics[:2] == ["Red Dead Redemption 2", "Elden Ring"] or critics[:2] == ["Elden Ring", "Red Dead Redemption 2"] or critics
    assert "Super Metroid" not in critics and "Hades" in critics  # sem nota da crítica, fora da lista
    assert api.get("/api/games?ordering=rating").get_json()["results"]
    assert api.get("/api/games?q=a").get_json()["ordering"] == "relevance"
    assert api.get("/api/games").get_json()["ordering"] == "popular"  # sem busca, "relevância" vira popularidade


def test_a_search_can_have_its_own_order(api):
    by_name = api.get("/api/games?q=hades&ordering=name").get_json()
    assert [g["name"] for g in by_name["results"]] == ["Hades", "Hades II"] and by_name["count"] == 2
    newest = api.get("/api/games?q=hades&ordering=released").get_json()
    assert [g["name"] for g in newest["results"]] == ["Hades II", "Hades"]
    page_two = api.get("/api/games?q=hades&ordering=name&per_page=1&page=2").get_json()
    assert [g["name"] for g in page_two["results"]] == ["Hades II"] and page_two["has_next"] is False
    assert api.get("/api/games?q=hades&ordering=name&per_page=1&page=1").get_json()["has_next"] is True


def test_a_listing_ignores_entries_that_are_not_games(api, monkeypatch):
    real = fake_igdb.fetch_json

    def noisy(query):
        data = real(query)
        if query.endpoint == "games" and not query.count:
            return [None, 7, {"name": "sem id"}, "texto", *data]
        return data

    monkeypatch.setattr(igdb, "fetch_json", noisy)
    names = [g["name"] for g in api.get("/api/games?q=hollow").get_json()["results"]]
    assert names == ["Hollow Knight"]


@pytest.mark.parametrize(
    "query",
    [
        "ordering=aleatorio", "ordering=metacritic", "year=abc", "year=1800", "year=3000", "genre=rpg;drop", "platform=abc",
        "page=0", "page=-1", "per_page=0", "per_page=500", "q=" + "x" * 101,
    ],
)
def test_catalog_validates_parameters(api, query):
    response = api.get(f"/api/games?{query}")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_a_search_with_special_characters_is_harmless(api):
    for term in ('"; where id = 1', "\\", "a;b", "' OR 1=1 --", "x" * 100):
        response = api.get("/api/games", query_string={"q": term})
        assert response.status_code == 200, term
    assert api.get("/api/games", query_string={"q": '";'}).get_json()["results"] == []


def test_genres_and_platforms_lookups(api):
    genres = api.get("/api/genres").get_json()["items"]
    assert {"id": 12, "name": "RPG", "slug": "role-playing-rpg"} in genres
    assert [g["name"] for g in genres] == sorted((g["name"] for g in genres), key=str.lower)
    platforms = api.get("/api/platforms").get_json()["items"]
    assert [p["name"] for p in platforms][:4] == ["PC", "PlayStation", "Xbox", "Nintendo"]
    assert {"id": 7, "name": "Nintendo", "slug": "nintendo"} in platforms


def test_featured_lists(api):
    body = api.get("/api/games/featured").get_json()
    assert body["errors"] == {}
    assert body["popular"] and body["new"]
    assert {g["name"] for g in body["new"]} <= {n for n, *_ in fake_igdb._FICTIONAL_NEW}
    assert [g["released"] for g in body["new"]] == sorted((g["released"] for g in body["new"]), reverse=True)


def test_featured_survives_a_partial_failure(api, monkeypatch):
    def only_popular(query):
        if query.sort == "first_release_date desc":
            raise igdb.IgdbUnavailable()
        return fake_igdb.fetch_json(query)

    monkeypatch.setattr(igdb, "fetch_json", only_popular)
    body = api.get("/api/games/featured").get_json()
    assert body["popular"] and body["new"] == [] and "new" in body["errors"]


def test_featured_fails_when_everything_fails(api, monkeypatch):
    def down(_query):
        raise igdb.IgdbUnavailable()

    monkeypatch.setattr(igdb, "fetch_json", down)
    assert api.get("/api/games/featured").status_code == 503


# ------------------------------------------------------------------ página do jogo
def test_game_page_combines_igdb_and_local_data(api):
    body = api.get(f"/api/games/{HADES}").get_json()
    game = body["game"]
    assert game["name"] == "Hades" and game["developers"] == ["Supergiant Games"] and game["publishers"] == ["Supergiant Games"]
    assert game["description"].startswith("Descrição de teste") and "<" not in game["description"]
    assert game["source"] == "igdb" and len(game["screenshots"]) == 3
    assert game["website"] == "https://hades.jogo.exemplo.com"  # a loja da Steam não vale como site oficial
    assert game["age_rating"] == {"label": "14 anos", "organization": "ClassInd"}
    assert game["critic_score"] == 93 and game["igdb_rating"] and game["igdb_ratings_count"] > 0
    assert game["cover_url"].endswith(f"/t_720p/co{HADES}.jpg") and game["cover_additional_url"].endswith(f"/t_1080p/ar{HADES}.jpg")
    assert "PC (Microsoft Windows)" in game["platforms"] and game["playtime"] is None
    assert body["notice"] is None and body["viewer"] is None
    assert body["community"]["count"] == 0 and body["community"]["average"] is None
    assert "age_ratings" not in game and "themes" not in game


def test_game_page_for_a_missing_game_is_404(api):
    response = api.get("/api/games/123456789")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "game_not_found"


def test_game_page_falls_back_to_local_data_when_igdb_is_down(ana, monkeypatch):
    ana.put(f"/api/library/{HADES}", {"status": "zerado"})
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Ótimo"})

    def down(_query):
        raise igdb.IgdbUnavailable()

    monkeypatch.setattr(igdb, "fetch_json", down)
    igdb.clear_cache()
    body = ana.get(f"/api/games/{HADES}").get_json()
    assert body["game"]["name"] == "Hades" and body["game"]["source"] == "local"
    assert body["game"]["age_rating"] is None and body["game"]["critic_score"] is None
    assert body["notice"]["code"] == "igdb_unavailable"
    assert body["community"]["average"] == 9 and body["reviews"][0]["body"] == "Ótimo"
    assert body["viewer"]["entry"]["status"] == "zerado"


def test_game_page_without_local_copy_and_igdb_down_reports_the_outage(api, monkeypatch):
    def down(_query):
        raise igdb.IgdbUnavailable()

    monkeypatch.setattr(igdb, "fetch_json", down)
    assert api.get(f"/api/games/{HADES}").status_code == 503


def test_a_game_without_screenshots_or_extras_still_has_a_page(api, monkeypatch):
    real = fake_igdb.fetch_json

    def bare(query):
        data = real(query)
        if ("id", "=", HADES) in query.filters and not query.count:
            return [{k: v for k, v in data[0].items() if k in ("id", "name", "slug")}]
        return data

    monkeypatch.setattr(igdb, "fetch_json", bare)
    game = api.get(f"/api/games/{HADES}").get_json()["game"]
    assert game["name"] == "Hades" and game["screenshots"] == [] and game["developers"] == [] and game["website"] is None


def test_top_rated_uses_only_community_reviews(ana, bruno, make_user):
    assert ana.get("/api/games/top-rated").get_json()["items"] == []
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 8})
    carla = make_user("carla")
    carla.play(HADES)
    carla.post(f"/api/games/{HADES}/reviews", {"rating": 8.5})
    body = ana.get("/api/games/top-rated").get_json()
    assert [(i["game"]["name"], i["average"], i["count"]) for i in body["items"]] == [("Hades", 8.5, 3)]
    assert body["min_notes"] == 3


def test_top_rated_needs_notes_from_three_different_people(ana, bruno, make_user):
    """Um 10 dado por uma ou duas pessoas não faz de um jogo o mais bem avaliado."""
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 10})
    assert ana.get("/api/games/top-rated").get_json()["items"] == []
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 10})
    assert ana.get("/api/games/top-rated").get_json()["items"] == []
    carla = make_user("carla")
    carla.play(HADES)
    carla.post(f"/api/games/{HADES}/reviews", {"rating": 10})
    items = ana.get("/api/games/top-rated").get_json()["items"]
    assert [(i["game"]["name"], i["count"]) for i in items] == [("Hades", 3)]


# ------------------------------------------------------------------- listas da página inicial
def test_featured_asks_for_more_than_it_shows_when_the_adult_filter_hides_games(app, monkeypatch):
    """No nível "mature" metade dos jogos mais votados some: a faixa busca mais para continuar cheia."""
    limits: dict[str, int] = {}
    real = fake_igdb.fetch_json

    def spy(query):
        if query.endpoint == "games" and not query.count:
            limits[app.config["ADULT_CONTENT_FILTER"]] = query.limit
        return real(query)

    monkeypatch.setattr(igdb, "fetch_json", spy)
    with app.app_context():
        for level in ("off", "explicit", "mature"):
            app.config["ADULT_CONTENT_FILTER"] = level
            igdb.clear_cache()
            data = igdb.featured_games("new", page_size=4)
            assert len(data["results"]) == 4 and data["page_size"] == 4
    assert limits == {"off": 4, "explicit": 12, "mature": 12}


def test_featured_fills_the_strip_with_the_games_that_pass_the_filter(app, monkeypatch):
    """Metade do que o IGDB devolve é adulto: sem a busca extra, a faixa de 6 ficaria com 3."""
    adult_game = fake_igdb.by_name("Jardim Proibido")
    normal = [g for g in fake_igdb.GAMES if g["name"] in {n for n, *_ in fake_igdb._FICTIONAL_NEW}]
    mixed = []
    for index, game in enumerate(normal[:6]):
        mixed += [game, {**adult_game, "id": 800000 + index, "name": f"Adulto {index}"}]
    real = fake_igdb.fetch_json

    def half_adult(query):
        if query.endpoint == "games" and not query.count and query.sort == "first_release_date desc":
            return [fake_igdb._project(g, query.fields) for g in mixed[: query.limit]]
        return real(query)

    monkeypatch.setattr(igdb, "fetch_json", half_adult)
    with app.app_context():
        data = igdb.featured_games("new", page_size=6)
    assert [g["name"] for g in data["results"]] == [g["name"] for g in normal[:6]]


def test_new_releases_need_a_few_ratings_so_unknown_entries_do_not_fill_the_strip(app, monkeypatch):
    yesterday = (date.today()).isoformat()
    unknown = fake_igdb._game(910001, "Cadastro Sem Votos", yesterday, "action", "pc", "X", None, 4)  # 1 voto
    noticed = fake_igdb._game(910002, "Jogo Com Votos", yesterday, "action", "pc", "X", None, 12)  # 3 votos
    monkeypatch.setattr(fake_igdb, "GAMES", [*fake_igdb.GAMES, unknown, noticed])
    with app.app_context():
        names = [g["name"] for g in igdb.featured_games("new")["results"]]
    assert "Jogo Com Votos" in names and "Cadastro Sem Votos" not in names
