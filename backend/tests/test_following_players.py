"""\"Quem você segue jogou\": o que a página do jogo mostra sobre as pessoas que a pessoa logada segue."""
from __future__ import annotations

from .conftest import CELESTE, HADES, HOLLOW


def following(client, rawg_id=HADES):
    return client.get(f"/api/games/{rawg_id}/following")


def names(body):
    return [item["user"]["username"] for item in body["items"]]


def test_it_needs_a_login(api):
    assert following(api).status_code == 401


def test_nobody_followed_means_an_empty_answer(ana, bruno):
    bruno.play(HADES)
    body = following(ana).get_json()  # a Ana não segue ninguém: o que o Bruno jogou não aparece
    assert body == {"items": [], "total": 0, "rated": 0, "average": None, "want_to_play": 0}


def test_a_game_nobody_registered_answers_empty_without_asking_the_rawg(ana, monkeypatch):
    from app.services import rawg

    def boom(*args, **kwargs):
        raise AssertionError("não deveria chamar a RAWG")

    monkeypatch.setattr(rawg, "fetch_json", boom)
    rawg.clear_cache()
    body = following(ana, HOLLOW).get_json()
    assert body["items"] == [] and body["total"] == 0


def test_lists_only_followed_people_with_status_favorite_and_rating(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES, status="jogando")
    carla.play(HADES)
    carla.put(f"/api/library/{HADES}", {"is_favorite": True})
    carla.post(f"/api/games/{HADES}/reviews", {"rating": 9.5, "body": "Ótimo."})
    ana.put("/api/users/carla/follow")  # a Ana segue a Carla, mas não o Bruno
    body = following(ana).get_json()
    assert names(body) == ["carla"]
    item = body["items"][0]
    assert item["status"] == "zerado" and item["is_favorite"] is True
    assert item["rating"] == 9.5 and item["has_text"] is True
    assert item["user"]["display_name"]
    assert "body" not in item and "email" not in item["user"]  # o texto da review e dados privados não vão junto
    assert body["total"] == 1 and body["rated"] == 1 and body["average"] == 9.5


def test_followed_people_who_only_want_to_play_are_counted_apart(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES, status="quero_jogar")
    carla.play(HADES)
    for name in ("bruno", "carla"):
        ana.put(f"/api/users/{name}/follow")
    body = following(ana).get_json()
    assert names(body) == ["carla"]  # quem só guardou na fila ainda não jogou
    assert body["total"] == 1 and body["want_to_play"] == 1


def test_a_rating_without_the_game_in_the_diary_still_counts_as_having_played(ana, bruno, app):
    from app.db import execute

    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 7})
    with app.app_context():  # nota antiga, de antes das regras do diário: o jogo saiu do diário e a nota ficou
        execute("DELETE FROM library_entries WHERE user_id = (SELECT id FROM users WHERE username = 'bruno')")
    ana.put("/api/users/bruno/follow")
    body = following(ana).get_json()
    assert names(body) == ["bruno"]
    assert body["items"][0]["status"] is None and body["items"][0]["rating"] == 7


def test_the_average_and_counts_cover_everyone_followed_not_just_the_first_twelve(ana, make_user):
    for number in range(14):
        person = make_user(f"pessoa{number:02d}")
        person.play(HADES)
        person.post(f"/api/games/{HADES}/reviews", {"rating": 8 if number % 2 == 0 else 6})
        ana.put(f"/api/users/pessoa{number:02d}/follow")
    body = following(ana).get_json()
    assert len(body["items"]) == 12
    assert body["total"] == 14 and body["rated"] == 14 and body["average"] == 7


def test_the_average_ignores_followed_people_who_did_not_rate(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES)
    carla.play(HADES)
    carla.post(f"/api/games/{HADES}/reviews", {"rating": 8})
    for name in ("bruno", "carla"):
        ana.put(f"/api/users/{name}/follow")
    body = following(ana).get_json()
    assert body["total"] == 2 and body["rated"] == 1 and body["average"] == 8


def test_most_recent_activity_comes_first(ana, bruno, make_user, app):
    from app.db import execute

    carla = make_user("carla")
    bruno.play(HADES)
    carla.play(HADES)
    ana.put("/api/users/bruno/follow")
    ana.put("/api/users/carla/follow")

    def touched(username, when):  # as datas fixas evitam depender do relógio (dois registros no mesmo segundo)
        with app.app_context():
            execute(
                "UPDATE library_entries SET updated_at = ? WHERE user_id = (SELECT id FROM users WHERE username = ?)",
                (when, username),
            )

    touched("bruno", "2026-01-01T10:00:00Z")
    touched("carla", "2026-01-02T10:00:00Z")
    assert names(following(ana).get_json()) == ["carla", "bruno"]
    touched("bruno", "2026-01-03T10:00:00Z")  # mexeu depois: passa à frente
    assert names(following(ana).get_json()) == ["bruno", "carla"]


def test_unfollowing_removes_the_person_and_other_games_are_not_mixed_in(ana, bruno):
    bruno.play(HADES)
    bruno.play(CELESTE)
    ana.put("/api/users/bruno/follow")
    assert names(following(ana, CELESTE).get_json()) == ["bruno"]
    assert names(following(ana, HOLLOW).get_json()) == []
    ana.delete("/api/users/bruno/follow")
    assert following(ana).get_json()["items"] == []


def test_demo_profiles_keep_their_mark(ana, app):
    from app import demo
    from app.db import fetch_one

    with app.app_context():
        demo.seed()
        row = fetch_one(
            "SELECT u.username, g.rawg_id FROM library_entries e JOIN users u ON u.id = e.user_id"
            " JOIN games g ON g.id = e.game_id WHERE u.is_demo = 1 AND e.status <> 'quero_jogar' ORDER BY e.id LIMIT 1"
        )
    ana.put(f"/api/users/{row['username']}/follow")
    body = following(ana, row["rawg_id"]).get_json()
    assert body["items"][0]["user"]["is_demo"] is True  # a marca "Exemplo" acompanha o perfil também aqui
