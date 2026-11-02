"""O início de quem está logado: "jogando agora" (um cartão por pessoa) e as novidades agrupadas em cartões."""
from __future__ import annotations

from app.db import execute

from .conftest import CELESTE, HADES, HOLLOW


def stamp(app, username, ts, *, type_=None, rawg_id=None, status=None):
    """Fixa a hora das atividades de uma pessoa (dois registros no mesmo segundo não têm ordem)."""
    where, params = ["user_id = (SELECT id FROM users WHERE username = ?)"], [username]
    if type_:
        where.append("type = ?")
        params.append(type_)
    if rawg_id:
        where.append("game_id = (SELECT id FROM games WHERE rawg_id = ?)")
        params.append(rawg_id)
    if status:
        where.append("status = ?")
        params.append(status)
    with app.app_context():
        execute(f"UPDATE activities SET created_at = ? WHERE {' AND '.join(where)}", (ts, *params))


def since(app, username, rawg_id, ts):
    with app.app_context():
        execute(
            "UPDATE library_entries SET status_changed_at = ? WHERE user_id = (SELECT id FROM users WHERE username = ?)"
            " AND game_id = (SELECT id FROM games WHERE rawg_id = ?)",
            (ts, username, rawg_id),
        )


def playing(client, scope="community", **query):
    extra = "".join(f"&{key}={value}" for key, value in query.items())
    return client.get(f"/api/playing?scope={scope}{extra}").get_json()


def highlights(client, scope="community", **query):
    extra = "".join(f"&{key}={value}" for key, value in query.items())
    return client.get(f"/api/highlights?scope={scope}{extra}").get_json()


def kinds(body):
    return [card["kind"] for card in body["items"]]


# ----------------------------------------------------------------------------- acesso
def test_both_endpoints_need_a_login(api):
    assert api.get("/api/playing").status_code == 401
    assert api.get("/api/highlights").status_code == 401


def test_the_scope_is_validated(ana):
    for path in ("/api/playing", "/api/highlights"):
        assert ana.get(f"{path}?scope=todos").status_code == 400
        assert ana.get(f"{path}?scope=").status_code == 400
        assert ana.get(path).status_code == 200  # sem o parâmetro vale a comunidade


# ----------------------------------------------------------------------------- jogando agora
def test_playing_has_one_card_per_person_with_the_game_started_most_recently(ana, bruno, app):
    bruno.play(HADES, status="jogando")
    bruno.play(CELESTE, status="jogando")
    since(app, "bruno", HADES, "2026-01-01T10:00:00Z")
    since(app, "bruno", CELESTE, "2026-01-02T10:00:00Z")
    body = playing(ana)
    assert len(body["items"]) == 1 and body["total"] == 1
    card = body["items"][0]
    assert card["game"]["rawg_id"] == CELESTE and card["also"] == 1
    assert card["user"]["username"] == "bruno" and "email" not in card["user"]
    assert card["since"] == "2026-01-02T10:00:00Z"


def test_playing_leaves_out_other_statuses_and_the_viewer_himself(ana, bruno):
    ana.play(HADES, status="jogando")  # o jogo de quem está vendo não entra
    bruno.play(CELESTE, status="zerado")
    bruno.play(HOLLOW, status="quero_jogar")
    assert playing(ana)["items"] == []


def test_following_scope_only_has_the_people_followed_and_counts_them(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES, status="jogando")
    carla.play(CELESTE, status="jogando")
    assert playing(ana, "following") == {"scope": "following", "items": [], "total": 0, "following": 0}
    ana.put("/api/users/bruno/follow")
    followed = playing(ana, "following")
    assert [card["user"]["username"] for card in followed["items"]] == ["bruno"]
    assert followed["following"] == 1
    everyone = playing(ana, "community")
    assert sorted(card["user"]["username"] for card in everyone["items"]) == ["bruno", "carla"]


def test_playing_is_ordered_by_who_started_most_recently_and_respects_the_limit(ana, make_user, app):
    for number, day in enumerate(("03", "01", "02")):
        person = make_user(f"pessoa{number}")
        person.play(HADES, status="jogando")
        since(app, f"pessoa{number}", HADES, f"2026-01-{day}T10:00:00Z")
    body = playing(ana)
    assert [card["user"]["username"] for card in body["items"]] == ["pessoa0", "pessoa2", "pessoa1"]
    limited = playing(ana, per_page=2)
    assert len(limited["items"]) == 2 and limited["total"] == 3


def test_playing_carries_the_start_date_when_there_is_one(ana, bruno):
    assert bruno.put(f"/api/library/{HADES}", {"status": "jogando", "started_at": "2026-01-10"}).status_code in (200, 201)
    assert playing(ana)["items"][0]["started_at"] == "2026-01-10"


# ----------------------------------------------------------------------------- novidades: zerou + avaliou
def finish_and_rate(person, rawg_id=HADES, rating=9, body="Ótimo."):
    person.play(rawg_id)
    return person.post(f"/api/games/{rawg_id}/reviews", {"rating": rating, "body": body})


def test_finishing_and_rating_the_same_game_is_one_card_with_the_note(ana, bruno):
    finish_and_rate(bruno, HADES, 9.5, "Uma obra-prima.")
    body = highlights(ana)
    assert kinds(body) == ["finished"]
    card = body["items"][0]
    assert card["game"]["rawg_id"] == HADES and card["rating"] == 9.5
    assert card["excerpt"] == "Uma obra-prima." and card["has_spoilers"] is False
    assert card["user"]["username"] == "bruno"


def test_finishing_without_a_review_is_a_card_without_a_note(ana, bruno):
    bruno.play(HADES)
    card = highlights(ana)["items"][0]
    assert card["kind"] == "finished" and card["rating"] is None and card["excerpt"] is None


def test_a_review_without_a_finish_in_the_window_is_its_own_card(ana, bruno, app):
    finish_and_rate(bruno)
    stamp(app, "bruno", "2026-01-01T10:00:00Z", type_="logged")  # o término foi bem antes da review
    stamp(app, "bruno", "2026-01-09T10:00:00Z", type_="reviewed")
    assert kinds(highlights(ana)) == ["reviewed", "finished"]
    stamp(app, "bruno", "2026-01-08T10:00:00Z", type_="logged")  # dentro de três dias: viram um cartão só
    assert kinds(highlights(ana)) == ["finished"]


def test_a_review_with_spoilers_never_shows_its_excerpt(ana, bruno):
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 8, "body": "O final é surpreendente.", "has_spoilers": True})
    card = highlights(ana)["items"][0]
    assert card["rating"] == 8 and card["has_spoilers"] is True and card["excerpt"] is None


def test_the_same_game_from_two_people_stays_two_cards(ana, bruno, make_user):
    carla = make_user("carla")
    finish_and_rate(bruno)
    finish_and_rate(carla, rating=7)
    assert sorted(card["user"]["username"] for card in highlights(ana)["items"]) == ["bruno", "carla"]


# ----------------------------------------------------------------------------- novidades: fila, status e o que fica de fora
def test_several_games_saved_in_a_row_become_one_queue_card(ana, bruno, app):
    for game in (HADES, CELESTE, HOLLOW):
        bruno.play(game, status="quero_jogar")
    stamp(app, "bruno", "2026-01-01T10:00:00Z", rawg_id=HADES)
    stamp(app, "bruno", "2026-01-01T11:00:00Z", rawg_id=CELESTE)
    stamp(app, "bruno", "2026-01-01T12:00:00Z", rawg_id=HOLLOW)
    body = highlights(ana)
    assert kinds(body) == ["queued"]
    card = body["items"][0]
    assert card["count"] == 3 and len(card["games"]) == 3
    assert card["games"][0]["rawg_id"] == HOLLOW  # a mais nova primeiro


def test_queue_cards_split_after_twelve_hours_and_show_at_most_four_covers(ana, bruno, app):
    for game in (HADES, CELESTE):
        bruno.play(game, status="quero_jogar")
    stamp(app, "bruno", "2026-01-01T01:00:00Z", rawg_id=HADES)
    stamp(app, "bruno", "2026-01-02T01:00:00Z", rawg_id=CELESTE)  # um dia depois
    assert kinds(highlights(ana)) == ["queued", "queued"]


def test_a_long_queue_run_counts_everything_but_shows_four_games(ana, bruno, app):
    from . import fake_rawg

    games = [game["id"] for game in fake_rawg.GAMES if game["name"] != "Farol do Amanhã"][:6]
    for game in games:
        bruno.play(game, status="quero_jogar")
    stamp(app, "bruno", "2026-01-01T10:00:00Z")
    card = highlights(ana)["items"][0]
    assert card["kind"] == "queued" and card["count"] == 6 and len(card["games"]) == 4


def test_queue_runs_of_different_people_do_not_mix(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES, status="quero_jogar")
    carla.play(HADES, status="quero_jogar")
    body = highlights(ana)
    assert kinds(body) == ["queued", "queued"] and all(card["count"] == 1 for card in body["items"])


def test_started_playing_is_not_news_but_giving_up_and_pausing_are(ana, bruno, make_user):
    carla = make_user("carla")
    bruno.play(HADES, status="jogando")
    assert highlights(ana)["items"] == []  # quem joga o quê agora está no "jogando agora"
    bruno.put(f"/api/library/{HADES}", {"status": "abandonado"})
    carla.play(CELESTE, status="jogando")
    carla.put(f"/api/library/{CELESTE}", {"status": "pausado"})
    body = highlights(ana)
    assert sorted(card["status"] for card in body["items"]) == ["abandonado", "pausado"]
    assert all(card["kind"] == "status" for card in body["items"])


def test_playing_again_is_not_news(ana, bruno):
    bruno.play(HADES)  # zerou
    assert bruno.post(f"/api/library/{HADES}/replay", {}).status_code == 201
    assert bruno.get(f"/api/games/{HADES}").get_json()["viewer"]["entry"]["status"] == "jogando"
    assert kinds(highlights(ana)) == ["finished"]  # só o "zerou" original, não o "voltou a jogar"
    assert playing(ana)["items"][0]["game"]["rawg_id"] == HADES  # e ele aparece no "jogando agora"


# ----------------------------------------------------------------------------- novidades: listas
def make_list(person, title, games=(), public=True):
    created = person.post("/api/lists", {"title": title, "is_public": public}).get_json()["list"]
    for game in games:
        assert person.post(f"/api/lists/{created['id']}/games", {"rawg_id": game}).status_code in (200, 201)
    return created


def test_a_public_list_with_games_is_a_card_with_its_covers(ana, bruno):
    make_list(bruno, "Roguelikes", [HADES, CELESTE])
    card = highlights(ana)["items"][0]
    assert card["kind"] == "list" and card["list"]["title"] == "Roguelikes"
    assert card["list"]["game_count"] == 2 and len(card["list"]["covers"]) == 2


def test_empty_and_private_lists_are_not_news(ana, bruno):
    make_list(bruno, "Vazia")
    make_list(bruno, "Particular", [HADES], public=False)
    assert highlights(ana)["items"] == []


# ----------------------------------------------------------------------------- escopo, dono e limite
def test_the_viewers_own_activity_is_left_out_and_following_filters_people(ana, bruno, make_user):
    carla = make_user("carla")
    ana.play(HADES)
    bruno.play(CELESTE)
    carla.play(HOLLOW)
    everyone = highlights(ana)
    assert sorted(card["user"]["username"] for card in everyone["items"]) == ["bruno", "carla"]
    assert highlights(ana, "following")["items"] == [] and highlights(ana, "following")["following"] == 0
    ana.put("/api/users/bruno/follow")
    followed = highlights(ana, "following")
    assert [card["user"]["username"] for card in followed["items"]] == ["bruno"] and followed["following"] == 1


def test_the_card_limit_applies_after_grouping(ana, make_user):
    for number in range(5):
        make_user(f"pessoa{number}").play(HADES)
    assert len(highlights(ana)["items"]) == 5
    assert len(highlights(ana, per_page=3)["items"]) == 3
    assert ana.get("/api/highlights?per_page=21").status_code == 400


def test_newest_cards_come_first(ana, bruno, make_user, app):
    carla = make_user("carla")
    bruno.play(HADES)
    carla.play(CELESTE)
    stamp(app, "bruno", "2026-01-01T10:00:00Z")
    stamp(app, "carla", "2026-01-02T10:00:00Z")
    assert [card["user"]["username"] for card in highlights(ana)["items"]] == ["carla", "bruno"]
