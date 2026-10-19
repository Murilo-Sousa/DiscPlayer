"""Esquema, restrições, índices, chaves estrangeiras e migrações do SQLite."""
from __future__ import annotations

import sqlite3

import pytest

from app import db as database
from app.utils.dates import utcnow_iso


@pytest.fixture
def conn(app):
    connection = database.connect(app.config["DATABASE"])
    yield connection
    connection.close()


def add_user(conn, name="ana"):
    return conn.execute(
        "INSERT INTO users (username, display_name, email, password_hash, created_at) VALUES (?, ?, ?, 'h', ?)",
        (name, name, f"{name}@x.co", utcnow_iso()),
    ).lastrowid


def add_game(conn, rawg_id=1):
    return conn.execute(
        "INSERT INTO games (rawg_id, name, slug, created_at) VALUES (?, 'G', 'g', ?)", (rawg_id, utcnow_iso())
    ).lastrowid


def test_every_connection_enables_foreign_keys_and_wal(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000


def test_expected_tables_exist(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {
        "users", "games", "library_entries", "reviews", "review_likes", "lists", "list_games", "follows",
        "activities", "schema_migrations",
    } <= tables


def test_frequent_queries_have_indexes(conn):
    indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {
        "ix_library_user_status", "ix_reviews_game_created", "ix_review_likes_review", "ix_list_games_order",
        "ix_follows_followed", "ix_activities_user",
    } <= indexes


def test_migrations_are_applied_once(app):
    assert database.migrate(app.config["DATABASE"]) == []  # já aplicadas na criação da app
    with sqlite3.connect(app.config["DATABASE"]) as raw:
        versions = [r[0] for r in raw.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert versions == ["0001_initial"]


def test_failed_migration_rolls_back_completely(tmp_path, monkeypatch):
    folder = tmp_path / "migrations"
    folder.mkdir()
    (folder / "0001_a.sql").write_text("CREATE TABLE a (id INTEGER PRIMARY KEY);")
    (folder / "0002_b.sql").write_text("CREATE TABLE b (id INTEGER PRIMARY KEY);\nCREATE TABLE a (id INTEGER);")
    monkeypatch.setattr(database, "MIGRATIONS_DIR", folder)
    path = tmp_path / "m.db"
    with pytest.raises(sqlite3.OperationalError):
        database.migrate(path)
    with sqlite3.connect(path) as raw:
        tables = {r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        applied = [r[0] for r in raw.execute("SELECT version FROM schema_migrations")]
    assert "a" in tables and "b" not in tables  # a segunda migração não deixou nada pela metade
    assert applied == ["0001_a"]


def test_foreign_keys_reject_orphans(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO library_entries (user_id, game_id, status, created_at, updated_at)"
            " VALUES (999, 999, 'jogando', 'x', 'x')"
        )


def test_library_entry_is_unique_per_user_and_game(conn):
    user, game = add_user(conn), add_game(conn)
    sql = (
        "INSERT INTO library_entries (user_id, game_id, status, created_at, updated_at)"
        " VALUES (?, ?, 'jogando', 'x', 'x')"
    )
    conn.execute(sql, (user, game))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, (user, game))


@pytest.mark.parametrize("rating", [7.3, -1, 10.5, 0.25])
def test_database_rejects_ratings_outside_the_scale(conn, rating):
    user, game = add_user(conn), add_game(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO reviews (user_id, game_id, rating, created_at) VALUES (?, ?, ?, 'x')", (user, game, rating)
        )


@pytest.mark.parametrize("rating", [0, 0.5, 5, 9.5, 10])
def test_database_accepts_ratings_on_the_scale(conn, rating):
    user, game = add_user(conn), add_game(conn)
    conn.execute("INSERT INTO reviews (user_id, game_id, rating, created_at) VALUES (?, ?, ?, 'x')", (user, game, rating))


def test_database_rejects_invalid_status_and_dates(conn):
    user, game = add_user(conn), add_game(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO library_entries (user_id, game_id, status, created_at, updated_at)"
            " VALUES (?, ?, 'terminado', 'x', 'x')", (user, game),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO library_entries (user_id, game_id, status, started_at, completed_at, created_at, updated_at)"
            " VALUES (?, ?, 'zerado', '2026-05-10', '2026-05-01', 'x', 'x')", (user, game),
        )


def test_self_follow_and_duplicate_follow_are_blocked_by_the_database(conn):
    a, b = add_user(conn, "ana"), add_user(conn, "bia")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, 'x')", (a, a))
    conn.execute("INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, 'x')", (a, b))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, 'x')", (a, b))


def test_duplicate_like_is_blocked_by_the_database(conn):
    user, game = add_user(conn), add_game(conn)
    other = add_user(conn, "bia")
    review = conn.execute(
        "INSERT INTO reviews (user_id, game_id, rating, created_at) VALUES (?, ?, 8, 'x')", (user, game)
    ).lastrowid
    conn.execute("INSERT INTO review_likes (user_id, review_id, created_at) VALUES (?, ?, 'x')", (other, review))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO review_likes (user_id, review_id, created_at) VALUES (?, ?, 'x')", (other, review))


def test_usernames_and_emails_are_unique_ignoring_case(conn):
    add_user(conn, "ana")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (username, display_name, email, password_hash, created_at)"
            " VALUES ('ANA', 'x', 'outro@x.co', 'h', 'x')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (username, display_name, email, password_hash, created_at)"
            " VALUES ('bia', 'x', 'ANA@X.CO', 'h', 'x')"
        )


def test_deleting_a_game_removes_everything_that_points_to_it(conn):
    user, game = add_user(conn), add_game(conn)
    lst = conn.execute(
        "INSERT INTO lists (user_id, title, created_at, updated_at) VALUES (?, 'L', 'x', 'x')", (user,)
    ).lastrowid
    conn.execute("INSERT INTO list_games (list_id, game_id, position, added_at) VALUES (?, ?, 0, 'x')", (lst, game))
    conn.execute(
        "INSERT INTO library_entries (user_id, game_id, status, created_at, updated_at) VALUES (?, ?, 'jogando', 'x', 'x')",
        (user, game),
    )
    conn.execute("DELETE FROM games WHERE id = ?", (game,))
    assert conn.execute("SELECT COUNT(*) FROM list_games").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM library_entries").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 1  # a lista em si permanece


def test_activity_rows_must_match_their_type(conn):
    user = add_user(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO activities (user_id, type, created_at) VALUES (?, 'logged', 'x')", (user,))


def test_data_survives_a_new_connection_and_a_new_app(app, ana):
    """Persistência: o que foi gravado continua lá para uma app nova sobre o mesmo arquivo."""
    from app import create_app
    from .conftest import HADES, Api

    ana.put(f"/api/library/{HADES}", {"status": "zerado"})
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "ficou"})
    restarted = Api(create_app({"TESTING": True, "DATABASE": app.config["DATABASE"], "RATELIMIT_ENABLED": False}))
    restarted.login("ana", "uma-senha-longa-123")
    assert restarted.get("/api/library").get_json()["counts"]["zerado"] == 1
    assert restarted.get("/api/users/ana/reviews").get_json()["items"][0]["body"] == "ficou"


def test_concurrent_writers_do_not_corrupt_data(app):
    """Várias threads gravando ao mesmo tempo: BEGIN IMMEDIATE + busy_timeout serializam as escritas."""
    import threading

    from .conftest import Api

    clients = []
    for index in range(6):
        client = Api(app)
        client.register(f"jogador{index}")
        clients.append(client)
    errors: list[int] = []

    def work(client):
        for rawg_id in range(900001, 900006):
            status = client.put(f"/api/library/{rawg_id}", {"status": "jogando"}).status_code
            if status not in (200, 201):
                errors.append(status)

    threads = [threading.Thread(target=work, args=(c,)) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with sqlite3.connect(app.config["DATABASE"]) as raw:
        assert raw.execute("SELECT COUNT(*) FROM library_entries").fetchone()[0] == 6 * 5
        assert raw.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
