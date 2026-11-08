"""Perfis de exemplo: criar, marcar, não deixar entrar, respeitar as regras do diário e sair de uma vez."""
from __future__ import annotations

import pytest

from app import create_app
from app import demo
from app.db import fetch_one
from app.services import igdb
from app.utils.dates import today_utc

from .conftest import PASSWORD
from .test_diary_rules import _violations, sql

USERNAMES = [person.username for person in demo.CAST]


@pytest.fixture
def seeded(app):
    with app.app_context():
        result = demo.seed()
    assert result["created"] is True
    return result


def test_seed_creates_the_cast_with_a_diary_reviews_lists_and_follows(app, seeded):
    assert seeded["users"] == len(USERNAMES) == 6
    assert seeded["reviews"] >= 25 and seeded["lists"] >= 3 and seeded["likes"] >= 10 and seeded["follows"] >= 10
    assert seeded["missing"] == []
    assert sql(app, "SELECT COUNT(*) FROM users WHERE is_demo = 1")[0][0] == 6


def test_every_demo_account_is_marked_and_the_public_api_says_so(app, seeded, api):
    profile = api.get("/api/users/marina_rpg").get_json()["user"]
    assert profile["is_demo"] is True
    reviews = api.get("/api/reviews?per_page=10").get_json()["items"]
    assert reviews and all(item["user"]["is_demo"] is True for item in reviews)
    activity = api.get("/api/activity?per_page=10").get_json()["items"]
    assert activity and all(item["user"]["is_demo"] is True for item in activity)
    assert api.get("/api/search?q=marina").get_json()["users"][0]["is_demo"] is True
    assert api.get("/api/lists").get_json()["items"][0]["owner"]["is_demo"] is True


def test_real_accounts_are_not_marked(app, seeded, make_user):
    ana = make_user("ana")
    assert ana.get("/api/users/ana").get_json()["user"]["is_demo"] is False


def test_demo_accounts_cannot_log_in_even_if_someone_set_a_known_password(app, seeded, api):
    for username in USERNAMES:
        assert api.post("/api/auth/login", {"identifier": username, "password": PASSWORD}).status_code == 401
        assert api.post("/api/auth/login", {"identifier": f"{username}@exemplo.invalid", "password": "x"}).status_code == 401
    # mesmo com uma senha conhecida (hash gravado à mão), o login recusa a conta de exemplo
    with app.app_context():
        from app.auth import hash_password

        known = hash_password(PASSWORD)
    sql(app, "UPDATE users SET password_hash = ? WHERE username = 'marina_rpg'", (known,))
    refused = api.post("/api/auth/login", {"identifier": "marina_rpg", "password": PASSWORD})
    assert refused.status_code == 401
    assert refused.get_json()["error"]["code"] == "invalid_credentials"


def test_the_demo_diary_follows_the_same_rules_as_a_real_one(app, seeded):
    assert _violations(app) == []
    # tudo o que tem nota está no diário como jogado, e nada tem data no futuro
    today = today_utc().isoformat()
    assert sql(app, "SELECT COUNT(*) FROM library_entries WHERE started_at > ? OR completed_at > ?", (today, today))[0][0] == 0
    assert sql(app, "SELECT COUNT(*) FROM reviews WHERE created_at > ?", (today + "T23:59:59Z",))[0][0] == 0
    assert sql(app, "SELECT COUNT(*) FROM reviews WHERE rating * 2 <> CAST(rating * 2 AS INTEGER)")[0][0] == 0


def test_dates_are_spread_over_time_instead_of_being_all_today(app, seeded):
    days = {row[0][:10] for row in sql(app, "SELECT created_at FROM reviews")}
    assert len(days) >= 15
    assert today_utc().isoformat() not in days  # nada nasce "agora": a atividade tem histórico


def test_the_ranking_and_the_community_numbers_come_out_of_the_demo_reviews(app, seeded, api):
    top = api.get("/api/games/top-rated").get_json()["items"]
    assert len(top) >= 3
    assert all(item["count"] >= 3 for item in top)
    assert [item["average"] for item in top] == sorted((item["average"] for item in top), reverse=True)


def test_one_demo_review_carries_the_spoiler_warning_and_stays_out_of_the_feed_excerpts(app, seeded, api):
    assert sql(app, "SELECT COUNT(*) FROM reviews WHERE has_spoilers = 1")[0][0] == 1
    activity = api.get("/api/users/tiago_indie/activity?per_page=30").get_json()["items"]
    flagged = [item["review"] for item in activity if item["type"] == "reviewed" and item["review"]["has_spoilers"]]
    assert len(flagged) == 1 and flagged[0]["excerpt"] is None  # o feed mostra o aviso, nunca o texto


def test_seed_twice_changes_nothing(app, seeded):
    before = sql(app, "SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM reviews), (SELECT COUNT(*) FROM activities)")[0]
    with app.app_context():
        assert demo.seed() == {"created": False, "users": 6, "stale": 0}
    assert tuple(sql(app, "SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM reviews), (SELECT COUNT(*) FROM activities)")[0]) == tuple(before)


def test_remove_takes_only_the_demo_profiles_and_everything_they_own(app, seeded, make_user):
    ana = make_user("ana")
    ana.play(900001)  # Hades
    review_id = ana.post("/api/games/900001/reviews", {"rating": 8, "body": "Gostei."}).get_json()["review"]["id"]
    # uma pessoa real curte e segue perfis de exemplo
    first = sql(app, "SELECT id FROM reviews WHERE user_id = (SELECT id FROM users WHERE username = 'tiago_indie') LIMIT 1")[0][0]
    assert ana.put(f"/api/reviews/{first}/like").status_code == 200
    assert ana.put("/api/users/tiago_indie/follow").status_code in (200, 201)

    with app.app_context():
        assert demo.remove() == 6
        assert demo.count() == 0
    assert sql(app, "SELECT COUNT(*) FROM users")[0][0] == 1
    for table in ("library_entries", "reviews", "lists", "follows", "review_likes", "list_games"):
        owners = sql(app, f"SELECT COUNT(*) FROM {table}")[0][0]
        assert owners == (1 if table in ("library_entries", "reviews") else 0), table
    assert ana.get(f"/api/reviews/{review_id}").status_code == 200  # a review da pessoa real continua
    assert ana.get("/api/users/tiago_indie").status_code == 404


def test_seed_refuses_when_a_real_account_already_uses_one_of_the_usernames(app):
    other = create_client_with_username(app, "bia_souls")
    assert other
    with app.app_context():
        with pytest.raises(demo.DemoError, match="bia_souls"):
            demo.seed()
        assert demo.count() == 0
    assert sql(app, "SELECT COUNT(*) FROM users")[0][0] == 1


def create_client_with_username(app, username):
    from .conftest import Api

    client = Api(app)
    client.register(username)
    return client


def test_seed_aborts_without_writing_anything_if_the_igdb_finds_no_games(app, monkeypatch):
    monkeypatch.setattr(demo, "_find_on_igdb", lambda name: (None, False))
    with app.app_context():
        with pytest.raises(demo.DemoError, match="Nada foi alterado"):
            demo.seed()
        assert demo.count() == 0
    assert sql(app, "SELECT COUNT(*) FROM users")[0][0] == 0


def test_a_game_the_igdb_does_not_find_is_skipped_and_reported(app, monkeypatch):
    original = demo._find_on_igdb
    monkeypatch.setattr(demo, "_find_on_igdb", lambda name: (None, False) if name == "Elden Ring" else original(name))
    with app.app_context():
        result = demo.seed()
    assert result["created"] is True and result["missing"] == ["Elden Ring"]
    assert _violations(app) == []
    assert sql(app, "SELECT COUNT(*) FROM games WHERE name = 'Elden Ring'")[0][0] == 0


def test_the_command_line_asks_for_confirmation_in_production(tmp_path, monkeypatch, capsys):
    from app.services import igdb
    from . import fake_igdb

    monkeypatch.setattr(igdb, "fetch_json", fake_igdb.fetch_json)
    igdb.clear_cache()
    production = create_app(
        {
            "IS_PRODUCTION": True,
            "SECRET_KEY": "p" * 40,
            "DATABASE": str(tmp_path / "prod.db"),
            "RATELIMIT_ENABLED": False,
            "IGDB_API_KEY": "chave-de-teste",
            "FRONTEND_DIST": str(tmp_path / "dist-inexistente"),
        }
    )
    monkeypatch.setattr("app.create_app", lambda: production)
    assert demo.main(["seed"]) == 2
    assert "--sim" in capsys.readouterr().err
    assert demo.main(["status"]) == 0  # só consultar não exige confirmação
    assert demo.main(["seed", "--sim"]) == 0
    assert "Criados 6 perfis" in capsys.readouterr().out
    assert demo.main(["remove", "--sim"]) == 0
    assert "Removidos 6 perfil" in capsys.readouterr().out


def test_every_demo_game_name_exists_in_the_fake_catalog():
    """O elenco só usa jogos que o IGDB de teste conhece (e, no uso real, a busca por nome os acha)."""
    from . import fake_igdb

    known = {game["name"] for game in fake_igdb.GAMES} if hasattr(fake_igdb, "GAMES") else None
    if known is None:  # o módulo expõe a lista com outro nome
        known = {g["name"] for g in fake_igdb._build()}
    missing = [name for name in demo._names_needed() if name not in known]
    assert missing == []


# ------------------------------------------------- troca de serviço (RAWG -> IGDB) e filtro de conteúdo adulto
def _demo_game_ids(app):
    return [r[0] for r in sql(app, "SELECT DISTINCT g.igdb_id FROM games g JOIN library_entries e ON e.game_id = g.id JOIN users u ON u.id = e.user_id WHERE u.is_demo = 1")]


def test_profiles_made_with_the_old_service_are_detected_and_refresh_remakes_them(app, seeded, make_user, capsys):
    ana = make_user("ana")
    ana.put("/api/library/%d" % _demo_game_ids(app)[0], {"status": "quero_jogar"})
    with app.app_context():
        assert demo.stale_games() == 0
    # o que a migração 0005 faz com os jogos guardados antes da troca: os números ficam negativos
    sql(app, "UPDATE games SET igdb_id = -igdb_id")
    with app.app_context():
        assert demo.stale_games() >= 15
        again = demo.seed()  # sem refresh, não mexe em nada, mas avisa
        assert again["created"] is False and again["stale"] >= 15
        demo._warn_if_stale()
    assert "python -m app.demo refresh" in capsys.readouterr().out
    assert all(i < 0 for i in _demo_game_ids(app))

    with app.app_context():
        result = demo.seed(replace=True)
        assert result["created"] is True and result["users"] == 6 and result["hidden"] == [] and result["missing"] == []
        assert demo.stale_games() == 0
    assert all(i > 0 for i in _demo_game_ids(app))
    assert sql(app, "SELECT COUNT(*) FROM users WHERE is_demo = 1")[0][0] == 6
    # a conta real e o diário dela ficaram como estavam
    assert sql(app, "SELECT COUNT(*) FROM users WHERE username = 'ana' AND is_demo = 0")[0][0] == 1
    assert sql(app, "SELECT COUNT(*) FROM library_entries e JOIN users u ON u.id = e.user_id WHERE u.username = 'ana'")[0][0] == 1
    # jogos antigos que ninguém mais usa foram embora; o que a conta real usa fica
    assert sql(app, "SELECT COUNT(*) FROM games WHERE igdb_id < 0")[0][0] == 1


def test_every_game_of_the_refreshed_profiles_opens(app, seeded, api):
    sql(app, "UPDATE games SET igdb_id = -igdb_id")
    with app.app_context():
        demo.seed(replace=True)
    ids = _demo_game_ids(app)
    assert len(ids) >= 15
    assert all(api.get(f"/api/games/{igdb_id}").status_code == 200 for igdb_id in ids)


def test_a_failed_refresh_changes_nothing(app, seeded, monkeypatch):
    def down(_query):
        raise igdb.IgdbUnavailable()

    monkeypatch.setattr(igdb, "fetch_json", down)
    with app.app_context(), pytest.raises(demo.DemoError, match="Nada foi alterado"):
        demo.seed(replace=True)
    assert sql(app, "SELECT COUNT(*) FROM users WHERE is_demo = 1")[0][0] == 6


def test_the_lookup_tells_a_game_that_does_not_exist_from_one_the_filter_hides(app):
    with app.app_context():
        assert demo._find_on_igdb("Hades")[1] is False
        assert demo._find_on_igdb("Jogo Que Nao Existe")  == (None, False)
        witcher_id, hidden = demo._find_on_igdb("The Witcher 3: Wild Hunt")
        assert witcher_id and hidden is False  # nível explicit: ESRB Mature aparece
        app.config["ADULT_CONTENT_FILTER"] = "mature"
        assert demo._find_on_igdb("The Witcher 3: Wild Hunt") == (witcher_id, True)


def test_with_the_mature_filter_the_cast_keeps_only_games_whose_page_opens(app, api):
    app.config["ADULT_CONTENT_FILTER"] = "mature"
    igdb.clear_cache()
    with app.app_context():
        result = demo.seed()
    assert result["created"] is True and result["users"] == 6
    assert {"The Witcher 3: Wild Hunt", "Elden Ring", "Disco Elysium"} <= set(result["hidden"])
    assert result["missing"] == []
    names = {r[0] for r in sql(app, "SELECT DISTINCT g.name FROM games g JOIN library_entries e ON e.game_id = g.id")}
    assert "Hades" in names and "Elden Ring" not in names and "The Witcher 3: Wild Hunt" not in names
    assert all(api.get(f"/api/games/{igdb_id}").status_code == 200 for igdb_id in _demo_game_ids(app))
    assert not _violations(app)  # as regras do diário continuam valendo para o que sobrou


def test_a_cast_the_filter_empties_out_is_refused_with_a_hint(app, monkeypatch):
    app.config["ADULT_CONTENT_FILTER"] = "mature"
    igdb.clear_cache()
    monkeypatch.setattr(demo, "MIN_GAMES", 100)
    with app.app_context(), pytest.raises(demo.DemoError, match="ADULT_CONTENT_FILTER=explicit"):
        demo.seed()
    assert sql(app, "SELECT COUNT(*) FROM users WHERE is_demo = 1")[0][0] == 0
