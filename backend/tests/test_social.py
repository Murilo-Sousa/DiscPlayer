"""Perfis públicos, seguir, feed e privacidade."""
from __future__ import annotations

from app.utils.dates import today_utc

from .conftest import CELESTE, HADES, HOLLOW


def log(client, rawg_id, status):
    assert client.put(f"/api/library/{rawg_id}", {"status": status}).status_code in (200, 201)


def test_follow_and_unfollow_are_idempotent(ana, bruno):
    first = ana.put("/api/users/bruno/follow")
    assert first.status_code == 200 and first.get_json() == {"following": True, "followers": 1}
    assert ana.put("/api/users/bruno/follow").get_json()["followers"] == 1  # sem duplicar
    profile = ana.get("/api/users/bruno").get_json()
    assert profile["viewer"] == {"is_self": False, "is_following": True}
    assert profile["stats"]["followers"] == 1
    assert ana.delete("/api/users/bruno/follow").get_json() == {"following": False, "followers": 0}
    assert ana.delete("/api/users/bruno/follow").get_json()["followers"] == 0


def test_cannot_follow_yourself(ana):
    response = ana.put("/api/users/ana/follow")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "cannot_follow_self"
    assert ana.get("/api/users/ana").get_json()["stats"]["followers"] == 0


def test_follow_unknown_user_is_404(ana):
    assert ana.put("/api/users/fantasma/follow").status_code == 404


def test_follower_and_following_lists(ana, bruno, make_user):
    carla = make_user("carla")
    ana.put("/api/users/carla/follow")
    bruno.put("/api/users/carla/follow")
    followers = ana.get("/api/users/carla/followers").get_json()["items"]
    assert [u["username"] for u in followers] == ["bruno", "ana"]
    assert [u["username"] for u in ana.get("/api/users/ana/following").get_json()["items"]] == ["carla"]
    assert all(set(u) <= {"username", "display_name", "avatar_url", "bio", "is_demo"} for u in followers)
    assert carla.get("/api/users/carla").get_json()["stats"]["following"] == 0


def test_feed_has_only_activity_from_followed_users(ana, bruno, make_user):
    carla = make_user("carla")
    log(bruno, HADES, "jogando")
    log(carla, CELESTE, "zerado")
    assert ana.get("/api/feed").get_json()["items"] == []  # ainda não segue ninguém
    ana.put("/api/users/bruno/follow")
    items = ana.get("/api/feed").get_json()["items"]
    assert [(i["user"]["username"], i["game"]["name"]) for i in items] == [("bruno", "Hades")]
    assert items[0]["type"] == "logged" and items[0]["status"] == "jogando"
    ana.delete("/api/users/bruno/follow")
    assert ana.get("/api/feed").get_json()["items"] == []


def test_feed_includes_reviews_and_public_lists_but_not_the_viewers_own_activity(ana, bruno):
    ana.put("/api/users/bruno/follow")
    bruno.play(HADES)
    bruno.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "Excelente " + "x" * 400})
    bruno.post("/api/lists", {"title": "Públicas"})
    bruno.post("/api/lists", {"title": "Privadas", "is_public": False})
    log(ana, CELESTE, "zerado")
    items = ana.get("/api/feed").get_json()["items"]
    kinds = sorted(i["type"] for i in items)
    assert kinds == ["list_created", "logged", "reviewed"]  # bruno registrou o jogo (para poder avaliá-lo)
    review = next(i for i in items if i["type"] == "reviewed")
    assert review["review"]["rating"] == 9
    assert review["review"]["excerpt"].endswith("…") and len(review["review"]["excerpt"]) <= 281
    assert [i["list"]["title"] for i in items if i["type"] == "list_created"] == ["Públicas"]


def test_global_activity_hides_private_lists_from_other_people(ana, bruno, api):
    bruno.post("/api/lists", {"title": "Segredo", "is_public": False})
    log(bruno, HADES, "jogando")
    assert "Segredo" not in str(api.get("/api/activity").get_json())
    assert "Segredo" not in str(ana.get("/api/users/bruno/activity").get_json())
    assert "Segredo" in str(bruno.get("/api/users/bruno/activity").get_json())


def test_activity_endpoints_are_read_only_and_cannot_impersonate(ana, bruno):
    response = ana.post("/api/activity", {"user": "bruno", "type": "logged"})
    assert response.status_code == 405
    # o autor de uma atividade é sempre quem está logado
    log(ana, HADES, "zerado")
    assert [a["user"]["username"] for a in bruno.get("/api/activity").get_json()["items"]] == ["ana"]


def test_public_profile_exposes_only_public_data(ana, bruno):
    ana.patch("/api/auth/me", {"display_name": "Ana S.", "bio": "Gosto de metroidvanias."})
    log(ana, HADES, "zerado")
    ana.post("/api/lists", {"title": "Segredo", "is_public": False})
    ana.post("/api/lists", {"title": "Aberta"})
    body = bruno.get("/api/users/ana").get_json()
    assert body["user"]["username"] == "ana" and body["user"]["bio"] == "Gosto de metroidvanias."
    assert body["user"]["created_at"]
    flat = str(body)
    for secret in ("ana@exemplo.com", "email", "password", "hash"):
        assert secret not in flat
    assert body["stats"]["lists"] == 1  # a privada não é contada para os outros
    assert ana.get("/api/users/ana").get_json()["stats"]["lists"] == 2
    assert body["viewer"]["is_self"] is False
    assert ana.get("/api/users/ana").get_json()["viewer"]["is_self"] is True


def test_profile_stats_are_computed_from_real_records(ana):
    log(ana, HADES, "zerado")
    log(ana, CELESTE, "zerado")
    log(ana, HOLLOW, "jogando")
    ana.put(f"/api/library/{HADES}", {"is_favorite": True})
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "ótimo"})
    ana.play(CELESTE)
    ana.post(f"/api/games/{CELESTE}/reviews", {"rating": 8})
    stats = ana.get("/api/users/ana").get_json()["stats"]
    assert stats["games"] == 3
    assert stats["by_status"] == {"quero_jogar": 0, "jogando": 1, "zerado": 2, "abandonado": 0, "pausado": 0}
    assert stats["favorites"] == 1
    assert stats["ratings"] == 2 and stats["reviews_with_text"] == 1
    assert stats["average_rating"] == 8.5
    assert stats["completed_this_year"] == 2
    month = today_utc().month  # o mesmo "hoje" do servidor (UTC): perto da meia-noite o dia local pode ser outro
    assert stats["completions_by_month"][month - 1] == 2 and sum(stats["completions_by_month"]) == 2
    assert stats["rating_distribution"][8] == 1  # a nota 8
    assert stats["rating_distribution"][9] == 1  # a nota 9
    assert sum(stats["rating_distribution"]) == 2


def test_profile_of_an_empty_account_has_zeroed_stats(ana):
    body = ana.get("/api/users/ana").get_json()
    assert body["stats"]["games"] == 0 and body["stats"]["average_rating"] is None
    assert body["favorites"] == [] and body["recent"] == []


def test_profile_shows_favorites_and_recent_entries(ana, bruno):
    log(ana, HADES, "zerado")
    log(ana, CELESTE, "jogando")
    ana.put(f"/api/library/{CELESTE}", {"is_favorite": True})
    body = bruno.get("/api/users/ana").get_json()
    assert [i["game"]["name"] for i in body["favorites"]] == ["Celeste"]
    assert {i["game"]["name"] for i in body["recent"]} == {"Hades", "Celeste"}


def test_username_lookup_is_case_insensitive_and_unknown_is_404(api, ana):
    assert api.get("/api/users/ANA").status_code == 200
    assert api.get("/api/users/ninguem").status_code == 404
    assert api.get("/api/users/ninguem/library").status_code == 404
    assert api.get("/api/users/ninguem/reviews").status_code == 404


def test_account_deletion_cascades_everywhere(ana, bruno, app):
    """Integridade referencial: apagar um usuário não deixa registros órfãos."""
    import sqlite3

    log(ana, HADES, "zerado")
    rid = ana.post(f"/api/games/{HADES}/reviews", {"rating": 9, "body": "boa"}).get_json()["review"]["id"]
    ana.post("/api/lists", {"title": "L"})
    ana.put("/api/users/bruno/follow")
    bruno.put(f"/api/reviews/{rid}/like")
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM users WHERE username = 'ana'")
    conn.commit()
    for table in ("library_entries", "reviews", "review_likes", "lists", "follows", "activities"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1  # o jogo continua no catálogo local
