"""`python -m app.igdb_check`: o relatório que confere o IGDB de verdade (aqui, contra o IGDB simulado)."""
from __future__ import annotations

import time

import pytest
import requests

from app import igdb_check
from app.services import adult, igdb

from . import fake_igdb

SECRETS = ("id-de-teste", "segredo-de-teste")


class Answer:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return self._payload

    def close(self):
        pass


@pytest.fixture
def twitch(app, monkeypatch):
    """O login da Twitch (a única chamada de rede que o simulado não cobre)."""
    igdb.clear_token()
    answers = {"login": Answer(payload={"access_token": "tok", "expires_in": 5_000_000})}
    monkeypatch.setattr(igdb._session, "post", lambda *a, **k: answers["login"])
    yield answers
    igdb.clear_token()


def report_of(app, **kwargs):
    lines: list[str] = []
    with app.app_context():
        code = igdb_check.run(lines.append, **kwargs)
    return code, "\n".join(lines)


def test_everything_checks_out_against_the_simulated_igdb(app, twitch):
    code, text = report_of(app, images=False)
    assert code == 0, text
    assert "✖" not in text
    for title in ("Login na Twitch", "Gêneros", "Plataformas", "Listas da página inicial", "Busca", "Filtros e ordens do catálogo",
                  "Página de um jogo", "Classificações etárias", "Filtro de conteúdo adulto", "Resumo"):
        assert title in text, title
    assert "0 falha(s)" in text
    assert "a Twitch aceitou as credenciais" in text
    assert "organizações vistas: ClassInd, ESRB, PEGI" in text
    assert "ficam escondidos no nível explicit" in text and "a página de um jogo adulto fica indisponível" in text


def test_the_report_never_shows_the_credentials_or_the_name_of_an_adult_game(app, twitch):
    _, text = report_of(app, images=False)
    assert not any(secret in text for secret in SECRETS)
    assert "tok" not in text.replace("token", "").replace("Fantasy", "")  # nem o token da Twitch
    for adult_game in ("Jardim Proibido", "Noite Sem Censura", "Quarto Dezoito"):
        assert adult_game not in text


def test_missing_credentials_are_explained_and_nothing_is_called(app, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("não devia chamar a rede")

    monkeypatch.setattr(igdb, "fetch_json", boom)
    monkeypatch.setattr(igdb._session, "post", boom)
    app.config["IGDB_CLIENT_SECRET"] = ""
    code, text = report_of(app)
    assert code == 2
    assert "faltam no backend/.env: IGDB_CLIENT_SECRET" in text
    assert "dev.twitch.tv/console" in text and "Resumo" not in text


def test_refused_credentials_stop_the_report_after_the_login(app, twitch):
    twitch["login"] = Answer(status=400, payload={"message": "invalid client secret"})
    code, text = report_of(app, images=False)
    assert code == 1
    assert "✖ A Twitch recusou as credenciais" in text
    assert "Sem o login não dá para continuar" in text
    assert "Gêneros" not in text  # as etapas seguintes nem começam


def test_one_failing_step_does_not_stop_the_others(app, twitch, monkeypatch):
    def broken():
        raise igdb.IgdbUnavailable("O IGDB demorou demais para responder.")

    monkeypatch.setattr(igdb, "list_genres", broken)
    code, text = report_of(app, images=False)
    assert code == 1
    genres = text.split("Gêneros")[1].split("Plataformas")[0]
    assert "✖ O IGDB demorou demais para responder." in genres
    assert "Página de um jogo" in text and "Filtro de conteúdo adulto" in text  # seguiram adiante
    assert text.count("✖ O IGDB demorou demais") >= 1 and "falha(s)" in text.split("Resumo")[1]


def test_what_the_igdb_said_about_a_refused_query_is_shown(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def picky(query):
        if query.endpoint == "platforms":
            raise igdb.IgdbUnavailable("O IGDB não entendeu a consulta.", detail='[{"title":"Syntax Error","cause":"campo x"}]')
        return real(query)

    monkeypatch.setattr(igdb, "fetch_json", picky)
    code, text = report_of(app, images=False)
    assert code == 1
    assert 'o IGDB disse: [{"title":"Syntax Error","cause":"campo x"}]' in text


def test_an_error_message_that_contains_the_secret_is_masked(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def leaky(query):
        if query.endpoint == "platforms":
            raise RuntimeError("falhou em https://x.example/?client_secret=segredo-de-teste&client_id=id-de-teste")
        return real(query)

    monkeypatch.setattr(igdb, "fetch_json", leaky)
    code, text = report_of(app, images=False)
    assert code == 1
    assert "RuntimeError" in text and "client_secret=***&client_id=***" in text
    assert not any(secret in text for secret in SECRETS)


def test_a_filter_that_lets_adult_games_through_is_reported_as_a_failure(app, twitch, monkeypatch):
    monkeypatch.setattr(adult, "block_reason", lambda raw, level: None)  # (is_blocked também passa por ela)
    code, text = report_of(app, images=False)
    assert code == 1
    assert "✖ 0 de 2 jogos com o tema “erotic” ficam escondidos no nível explicit" in text
    assert "✖ a busca pelo nome de um jogo adulto ainda o devolve" in text
    assert "✖ a página de um jogo adulto abriu" in text


def test_with_the_filter_off_the_report_says_so_instead_of_failing(app, twitch):
    app.config["ADULT_CONTENT_FILTER"] = "off"
    igdb.clear_cache()
    code, text = report_of(app, images=False)
    block = text.split("Filtro de conteúdo adulto")[1]
    assert "nível do filtro em uso: off" in block
    assert "o filtro está desligado (off)" in block and "a página de um jogo adulto abre (filtro desligado)" in block
    assert "✖ a busca" not in block and "✖ a página" not in block


def test_an_age_rating_in_a_shape_nobody_understands_is_reported_with_an_example(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def odd(query):
        data = real(query)
        if query.endpoint == "games" and not query.count and "age_ratings.organization.name" in query.fields and query.limit == 40 and not any(
            f[0] == "themes" for f in query.filters
        ):
            data[0]["age_ratings"] = [{"organizacao": "ESRB", "nota": "M"}]
        return data

    monkeypatch.setattr(igdb, "fetch_json", odd)
    code, text = report_of(app, images=False)
    assert code == 1
    assert "✖ há classificações num formato que o filtro não entende. Exemplo: {'organizacao': 'ESRB', 'nota': 'M'}" in text


def test_an_organization_the_filter_does_not_know_is_a_warning(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def new_org(query):
        data = real(query)
        if query.endpoint == "games" and not query.count and query.limit == 40 and "themes.slug" not in query.fields:
            data[0]["age_ratings"] = [{"organization": {"name": "Organização Nova"}, "rating_category": {"rating": "18"}}]
        return data

    monkeypatch.setattr(igdb, "fetch_json", new_org)
    code, text = report_of(app, images=False)
    assert code == 0
    assert "⚠ organizações que o filtro ainda não conhece (não escondem nada): Organização Nova" in text


def test_a_theme_number_that_changed_meaning_is_reported(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def moved(query):
        if query.endpoint == "themes":
            return [{"id": 42, "name": "Outro", "slug": "outro"}]
        return real(query)

    monkeypatch.setattr(igdb, "fetch_json", moved)
    code, text = report_of(app, images=False)
    assert code == 1
    assert "✖ o tema número 42 do IGDB agora é “outro”" in text


def test_genres_without_a_translation_are_listed_as_a_warning(app, twitch, monkeypatch):
    real = fake_igdb.fetch_json

    def extra(query):
        data = real(query)
        if query.endpoint == "genres":
            data = data + [{"id": 99, "name": "Gênero Novo", "slug": "genero-novo"}]
        return data

    monkeypatch.setattr(igdb, "fetch_json", extra)
    code, text = report_of(app, images=False)
    assert code == 0
    assert "⚠ gêneros que aparecem com o nome em inglês (sem tradução): genero-novo" in text


def test_the_token_lifetime_is_reported_in_days(app, twitch):
    _, text = report_of(app, images=False)
    assert "o token vale por cerca de 57 dias" in text or "o token vale por cerca de 58 dias" in text
    assert igdb._token["expires_at"] > time.monotonic()


# ------------------------------------------------------------------------------------------------ as imagens
def test_the_cover_check_downloads_a_cover_and_reports_the_type(app, twitch, monkeypatch):
    asked: list[str] = []

    def get(url, **_kwargs):
        asked.append(url)
        return Answer(headers={"Content-Type": "image/jpeg"})

    monkeypatch.setattr(igdb_check.requests, "get", get)
    code, text = report_of(app)
    assert code == 0, text
    assert len(asked) == 2 and all(u.startswith("https://images.igdb.com/igdb/image/upload/") for u in asked)
    assert "✔ a capa abre (image/jpeg)" in text


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (Answer(status=403, headers={"Content-Type": "text/html"}), "a capa respondeu HTTP 403"),
        (Answer(status=200, headers={"Content-Type": "text/html"}), "a capa respondeu HTTP 200 (text/html)"),
        (requests.ReadTimeout("demorou demais"), "não consegui baixar uma capa (ReadTimeout)"),
    ],
)
def test_a_cover_that_does_not_open_is_a_failure(app, twitch, monkeypatch, outcome, expected):
    def get(url, **_kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(igdb_check.requests, "get", get)
    code, text = report_of(app)
    assert code == 1
    assert expected in text


@pytest.mark.parametrize("error", [requests.ConnectionError("sem rede"), requests.exceptions.ProxyError("403 Forbidden")])
def test_a_host_that_cannot_reach_the_cover_server_gets_a_warning_not_a_failure(app, twitch, monkeypatch, error):
    # Caso real: no plano gratuito da PythonAnywhere o servidor não alcança images.igdb.com (ProxyError),
    # mas o site funciona, porque as capas são baixadas pelo navegador de quem visita.
    asked: list[str] = []

    def get(url, **_kwargs):
        asked.append(url)
        raise error

    monkeypatch.setattr(igdb_check.requests, "get", get)
    code, text = report_of(app)
    assert code == 0, text
    assert len(asked) == 1  # não insiste: uma tentativa basta para saber
    assert "este servidor não alcança as capas" in text
    assert "quem baixa as capas é o navegador" in text
    assert "0 falha(s)" in text
