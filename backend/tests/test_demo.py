"""Perfis de exemplo: criar, marcar, não deixar entrar, respeitar as regras do diário e sair de uma vez."""
from __future__ import annotations

import pytest

from app import create_app
from app import demo
from app.db import fetch_one
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
        assert demo.seed() == {"created": False, "users": 6}
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


def test_seed_aborts_without_writing_anything_if_the_rawg_finds_no_games(app, monkeypatch):
    monkeypatch.setattr(demo, "_find_on_rawg", lambda name: None)
    with app.app_context():
        with pytest.raises(demo.DemoError, match="Nada foi criado"):
            demo.seed()
        assert demo.count() == 0
    assert sql(app, "SELECT COUNT(*) FROM users")[0][0] == 0


def test_a_game_the_rawg_does_not_find_is_skipped_and_reported(app, monkeypatch):
    original = demo._find_on_rawg
    monkeypatch.setattr(demo, "_find_on_rawg", lambda name: None if name == "Elden Ring" else original(name))
    with app.app_context():
        result = demo.seed()
    assert result["created"] is True and result["missing"] == ["Elden Ring"]
    assert _violations(app) == []
    assert sql(app, "SELECT COUNT(*) FROM games WHERE name = 'Elden Ring'")[0][0] == 0


def test_the_command_line_asks_for_confirmation_in_production(tmp_path, monkeypatch, capsys):
    from app.services import rawg
    from . import fake_rawg

    monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
    rawg.clear_cache()
    production = create_app(
        {
            "IS_PRODUCTION": True,
            "SECRET_KEY": "p" * 40,
            "DATABASE": str(tmp_path / "prod.db"),
            "RATELIMIT_ENABLED": False,
            "RAWG_API_KEY": "chave-de-teste",
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
    """O elenco só usa jogos que a RAWG de teste conhece (e, no uso real, a busca por nome os acha)."""
    from . import fake_rawg

    known = {game["name"] for game in fake_rawg.GAMES} if hasattr(fake_rawg, "GAMES") else None
    if known is None:  # o módulo expõe a lista com outro nome
        known = {g["name"] for g in fake_rawg._build()}
    missing = [name for name in demo._names_needed() if name not in known]
    assert missing == []
