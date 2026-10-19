"""Integração com a RAWG: transporte, erros, cache, normalização e rotas do catálogo."""
from __future__ import annotations

import logging

import pytest
import requests

from app.services import rawg

from . import fake_rawg
from .conftest import HADES


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, text_json=True):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self._text_json = text_json

    def json(self):
        if not self._text_json:
            raise ValueError("não é JSON")
        return self._payload


@pytest.fixture
def real_transport(app, monkeypatch):
    """Usa o fetch_json de verdade, com a camada HTTP substituída."""
    monkeypatch.undo()  # remove o patch do conftest em fetch_json
    rawg.clear_cache()
    calls: list[dict] = []
    outcome: dict = {"response": FakeResponse()}

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append({"url": url, "params": dict(params or {}), "timeout": timeout, "headers": headers})
        result = outcome["response"]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(rawg._session, "get", fake_get)
    return calls, outcome


def call(path="games", params=None):
    from flask import current_app  # noqa: F401  (apenas garante o contexto da app)

    return rawg.fetch_json(path, params)


# ---------------------------------------------------------------- transporte e erros
def test_request_sends_key_server_side_with_a_timeout(app, real_transport):
    calls, outcome = real_transport
    outcome["response"] = FakeResponse(payload={"results": []})
    with app.app_context():
        assert rawg.fetch_json("games", {"page": 1}) == {"results": []}
    sent = calls[0]
    assert sent["url"] == "https://api.rawg.io/api/games"
    assert sent["params"]["key"] == "chave-de-teste" and sent["params"]["page"] == 1
    assert sent["timeout"] and all(t > 0 for t in sent["timeout"])


@pytest.mark.parametrize(
    "response, error_type, status, code",
    [
        (FakeResponse(404), rawg.RawgNotFound, 404, "game_not_found"),
        (FakeResponse(401), rawg.RawgNotConfigured, 503, "rawg_not_configured"),
        (FakeResponse(403), rawg.RawgNotConfigured, 503, "rawg_not_configured"),
        (FakeResponse(429, headers={"Retry-After": "30"}), rawg.RawgRateLimited, 429, "rawg_rate_limited"),
        (FakeResponse(500), rawg.RawgUnavailable, 503, "rawg_unavailable"),
        (FakeResponse(502), rawg.RawgUnavailable, 503, "rawg_unavailable"),
        (FakeResponse(200, text_json=False), rawg.RawgUnavailable, 503, "rawg_unavailable"),
        (requests.Timeout("lento"), rawg.RawgUnavailable, 503, "rawg_unavailable"),
        (requests.ConnectionError("sem rede"), rawg.RawgUnavailable, 503, "rawg_unavailable"),
    ],
)
def test_http_failures_become_specific_errors(app, real_transport, response, error_type, status, code):
    _, outcome = real_transport
    outcome["response"] = response
    with app.app_context(), pytest.raises(error_type) as caught:
        rawg.fetch_json("games")
    assert caught.value.status == status and caught.value.code == code


def test_rate_limit_error_carries_retry_after(app, real_transport):
    _, outcome = real_transport
    outcome["response"] = FakeResponse(429, headers={"Retry-After": "42"})
    with app.app_context(), pytest.raises(rawg.RawgRateLimited) as caught:
        rawg.fetch_json("games")
    assert caught.value.retry_after == 42


def test_missing_key_fails_before_any_network_call(app, real_transport):
    calls, _ = real_transport
    app.config["RAWG_API_KEY"] = ""
    with app.app_context(), pytest.raises(rawg.RawgNotConfigured):
        rawg.fetch_json("games")
    assert calls == []


def test_routes_translate_rawg_errors_into_clean_json(api, real_transport):
    _, outcome = real_transport
    outcome["response"] = FakeResponse(429, headers={"Retry-After": "12"})
    response = api.get("/api/games?q=hades")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "12"
    assert response.get_json()["error"]["code"] == "rawg_rate_limited"
    outcome["response"] = requests.Timeout("x")
    rawg.clear_cache()
    assert api.get("/api/games?q=hades").status_code == 503


def test_api_key_never_leaks_in_logs_or_responses(app, api, real_transport, caplog):
    _, outcome = real_transport
    outcome["response"] = requests.ConnectionError("HTTPSConnectionPool: /api/games?key=chave-de-teste")
    with caplog.at_level(logging.DEBUG):
        response = api.get("/api/games?q=zelda")
    assert "chave-de-teste" not in response.get_data(as_text=True)
    assert "chave-de-teste" not in caplog.text


def test_health_reports_whether_rawg_is_configured_without_revealing_the_key(api):
    body = api.get("/api/health").get_json()
    assert body["rawg_configured"] is True
    assert "chave-de-teste" not in str(body)


# -------------------------------------------------------------------------- cache
def test_cache_avoids_repeated_requests_and_serves_stale_data_when_rawg_fails(app, monkeypatch):
    hits = {"n": 0}

    def counting(path, params=None):
        hits["n"] += 1
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", counting)
    with app.app_context():
        rawg.search_games(search="hades")
        rawg.search_games(search="hades")
        assert hits["n"] == 1
        rawg.search_games(search="celeste")
        assert hits["n"] == 2

        # expira o cache (mas ele continua servível como cópia obsoleta) e derruba a RAWG
        app.config["RAWG_TTL_SEARCH"] = 0
        rawg.clear_cache()
        rawg.search_games(search="hades")
        before = hits["n"]

        def down(*_a, **_k):
            raise rawg.RawgUnavailable()

        monkeypatch.setattr(rawg, "fetch_json", down)
        stale = rawg.search_games(search="hades")
        assert stale["results"][0]["name"] == "Hades"
        assert hits["n"] == before


def test_failures_are_not_cached(app, monkeypatch):
    state = {"fail": True}

    def flaky(path, params=None):
        if state["fail"]:
            raise rawg.RawgUnavailable()
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", flaky)
    with app.app_context():
        with pytest.raises(rawg.RawgUnavailable):
            rawg.search_games(search="hades")
        state["fail"] = False
        assert rawg.search_games(search="hades")["results"]


# ---------------------------------------------------------------- normalização
def test_normalization_tolerates_missing_fields():
    summary = rawg.normalize_summary({"id": 1})
    assert summary["name"] == "Sem título"
    assert summary["cover_url"] is None and summary["cover_thumb_url"] is None
    assert summary["released"] is None and summary["genres"] == [] and summary["platforms"] == []
    assert summary["metacritic"] is None
    detail = rawg.normalize_detail({"id": 1, "name": "X"})
    assert detail["description"] == "" and detail["developers"] == []
    assert detail["rawg_rating"] is None and detail["rawg_ratings_count"] == 0


@pytest.mark.parametrize("raw", [{}, {"id": "7"}, {"id": None}, {"id": True}, {"name": "sem id"}])
def test_entries_without_a_valid_id_are_dropped(raw):
    assert rawg.normalize_summary(raw) is None


@pytest.mark.parametrize(
    "url",
    ["http://media.rawg.io/a.jpg", "javascript:alert(1)", "data:image/png;base64,AAAA", "//evil.example/a.jpg", "", None, 42, "https://" + "a" * 700],
)
def test_only_https_images_are_accepted(url):
    assert rawg.safe_image_url(url) is None


def test_thumbnail_url_uses_rawg_crop_and_leaves_other_hosts_alone():
    assert rawg.thumb_url("https://media.rawg.io/media/games/abc/x.jpg") == "https://media.rawg.io/media/crop/600/400/games/abc/x.jpg"
    assert rawg.thumb_url("https://cdn.exemplo.com/x.jpg") == "https://cdn.exemplo.com/x.jpg"
    assert rawg.thumb_url(None) is None


def test_invalid_release_dates_are_dropped():
    assert rawg.normalize_summary({"id": 1, "released": "tba"})["released"] is None
    assert rawg.normalize_summary({"id": 1, "released": "2020-02-30"})["released"] is None
    assert rawg.normalize_summary({"id": 1, "released": "2020-02-29"})["released"] == "2020-02-29"


def test_html_descriptions_are_reduced_to_plain_text():
    detail = rawg.normalize_detail(
        {"id": 1, "name": "X", "description": "<p>Olá <script>alert(1)</script><b>mundo</b></p><p>Fim &amp; tudo</p>"}
    )
    assert "<" not in detail["description"] and "alert" not in detail["description"]
    assert detail["description"] == "Olá mundo\n\nFim & tudo"


def test_unsafe_website_urls_are_dropped():
    assert rawg.normalize_detail({"id": 1, "website": "javascript:alert(1)"})["website"] is None
    assert rawg.normalize_detail({"id": 1, "website": "https://jogo.exemplo.com"})["website"] == "https://jogo.exemplo.com"


# ------------------------------------------------------------------ rotas do catálogo
def test_catalog_search_pagination_and_shape(api):
    body = api.get("/api/games?q=hollow&per_page=5").get_json()
    assert [g["name"] for g in body["results"]] == ["Hollow Knight"]
    first = api.get("/api/games?page=1&per_page=10").get_json()
    second = api.get("/api/games?page=2&per_page=10").get_json()
    assert len(first["results"]) == 10 and first["has_next"] is True and first["has_previous"] is False
    assert second["has_previous"] is True
    assert {g["rawg_id"] for g in first["results"]}.isdisjoint({g["rawg_id"] for g in second["results"]})
    game = first["results"][0]
    assert {"rawg_id", "name", "slug", "cover_url", "cover_thumb_url", "released", "genres", "platforms"} <= set(game)


def test_catalog_filters(api):
    rpg = api.get("/api/games?genre=rpg&per_page=40").get_json()["results"]
    assert rpg and all("RPG" in g["genres"] for g in rpg)
    nintendo = api.get("/api/games?platform=7&per_page=40").get_json()["results"]
    assert nintendo and all("Nintendo" in g["platforms"] for g in nintendo)
    in_2018 = api.get("/api/games?year=2018&per_page=40").get_json()["results"]
    assert {g["name"] for g in in_2018} >= {"Celeste", "God of War"}
    assert all(g["released"].startswith("2018") for g in in_2018)


def test_catalog_orderings(api):
    released = [g["released"] for g in api.get("/api/games?ordering=released&per_page=40").get_json()["results"]]
    assert released == sorted(released, reverse=True)
    names = [g["name"] for g in api.get("/api/games?ordering=name&per_page=40").get_json()["results"]]
    assert names == sorted(names, key=str.lower)
    assert api.get("/api/games?q=a").get_json()["ordering"] == "relevance"
    assert api.get("/api/games").get_json()["ordering"] == "popular"  # sem busca, "relevância" vira popularidade


@pytest.mark.parametrize(
    "query",
    [
        "ordering=aleatorio", "year=abc", "year=1800", "year=3000", "genre=rpg;drop", "platform=abc",
        "page=0", "page=-1", "per_page=0", "per_page=500", "q=" + "x" * 101,
    ],
)
def test_catalog_validates_parameters(api, query):
    response = api.get(f"/api/games?{query}")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_genres_and_platforms_lookups(api):
    assert {"id": 5, "name": "RPG", "slug": "rpg"} in api.get("/api/genres").get_json()["items"]
    assert any(p["name"] == "PlayStation" for p in api.get("/api/platforms").get_json()["items"])


def test_featured_lists(api):
    body = api.get("/api/games/featured").get_json()
    assert body["errors"] == {}
    assert body["popular"] and body["new"]
    assert {g["name"] for g in body["new"]} <= {n for n, *_ in fake_rawg._FICTIONAL_NEW}


def test_featured_survives_a_partial_failure(api, monkeypatch):
    def only_popular(path, params=None):
        if params and params.get("ordering") == "-released":
            raise rawg.RawgUnavailable()
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", only_popular)
    body = api.get("/api/games/featured").get_json()
    assert body["popular"] and body["new"] == [] and "new" in body["errors"]


def test_featured_fails_when_everything_fails(api, monkeypatch):
    def down(*_a, **_k):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    assert api.get("/api/games/featured").status_code == 503


# ------------------------------------------------------------------ página do jogo
def test_game_page_combines_rawg_and_local_data(api):
    body = api.get(f"/api/games/{HADES}").get_json()
    game = body["game"]
    assert game["name"] == "Hades" and game["developers"] == ["Supergiant Games"]
    assert game["description"].startswith("Descrição de teste")
    assert "<" not in game["description"]
    assert game["source"] == "rawg" and len(game["screenshots"]) == 3
    assert body["notice"] is None and body["viewer"] is None
    assert body["community"]["count"] == 0
    assert body["community"]["average"] is None


def test_game_page_for_a_missing_game_is_404(api):
    assert api.get("/api/games/123456789").status_code == 404


def test_game_page_falls_back_to_local_data_when_rawg_is_down(ana, monkeypatch):
    ana.put(f"/api/library/{HADES}", {"status": "zerado"})
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Ótimo"})

    def down(*_a, **_k):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    rawg.clear_cache()
    body = ana.get(f"/api/games/{HADES}").get_json()
    assert body["game"]["name"] == "Hades" and body["game"]["source"] == "local"
    assert body["notice"]["code"] == "rawg_unavailable"
    assert body["community"]["average"] == 9 and body["reviews"][0]["body"] == "Ótimo"
    assert body["viewer"]["entry"]["status"] == "zerado"


def test_game_page_without_local_copy_and_rawg_down_reports_the_outage(api, monkeypatch):
    def down(*_a, **_k):
        raise rawg.RawgUnavailable()

    monkeypatch.setattr(rawg, "fetch_json", down)
    assert api.get(f"/api/games/{HADES}").status_code == 503


def test_game_page_screenshot_failure_does_not_break_the_page(api, monkeypatch):
    def no_shots(path, params=None):
        if path.endswith("/screenshots"):
            raise rawg.RawgUnavailable()
        return fake_rawg.fetch_json(path, params)

    monkeypatch.setattr(rawg, "fetch_json", no_shots)
    body = api.get(f"/api/games/{HADES}").get_json()
    assert body["game"]["screenshots"] == []


def test_top_rated_uses_only_community_reviews(ana, bruno):
    assert ana.get("/api/games/top-rated").get_json()["items"] == []
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9})
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 8})
    items = ana.get("/api/games/top-rated").get_json()["items"]
    assert [(i["game"]["name"], i["average"], i["count"]) for i in items] == [("Hades", 8.5, 2)]
