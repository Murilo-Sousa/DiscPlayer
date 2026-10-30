"""Notas, reviews, médias da comunidade e curtidas."""
from __future__ import annotations

import pytest

from . import fake_rawg
from .conftest import CELESTE, HADES


def review(client, rawg_id=HADES, **body):
    client.play(rawg_id)  # só avalia quem já jogou
    return client.post(f"/api/games/{rawg_id}/reviews", body)


def test_create_review_with_text(ana):
    response = review(ana, rating=8.5, body="Cada fuga é diferente.")
    assert response.status_code == 201
    data = response.get_json()["review"]
    assert data["rating"] == 8.5
    assert data["body"] == "Cada fuga é diferente."
    assert data["user"]["username"] == "ana"
    assert data["game"]["name"] == "Hades"
    assert data["like_count"] == 0 and data["liked"] is False
    assert data["created_at"] and data["updated_at"] is None
    assert "email" not in data["user"]


def test_rating_only_review_is_allowed(ana):
    data = review(ana, rating=7).get_json()["review"]
    assert data["body"] is None


def test_blank_text_counts_as_no_text(ana):
    assert review(ana, rating=7, body="   \n  ").get_json()["review"]["body"] is None


@pytest.mark.parametrize("rating", [0, 0.5, 5, 9.5, 10, "7,5", "8.0", 3.0])
def test_valid_ratings(ana, rating):
    assert review(ana, rating=rating).status_code == 201


@pytest.mark.parametrize("rating", [7.3, 10.5, -0.5, -1, 11, "abc", "", True, False, [], {}, float("nan")])
def test_invalid_ratings_are_rejected_by_the_server(ana, rating):
    response = review(ana, rating=rating)
    assert response.status_code == 422
    assert "rating" in response.get_json()["error"]["fields"]


def test_rating_is_required(ana):
    response = review(ana, body="só texto")
    assert response.status_code == 422
    assert "rating" in response.get_json()["error"]["fields"]


def test_text_length_limit(ana):
    assert review(ana, rating=5, body="x" * 5001).status_code == 422
    assert review(ana, rating=5, body="x" * 5000).status_code == 201


def test_text_is_stored_as_plain_data_and_control_characters_are_removed(ana):
    data = review(ana, rating=5, body="<script>alert(1)</script>\x00 oi‮").get_json()["review"]
    assert data["body"] == "<script>alert(1)</script> oi"  # o React escapa na hora de exibir


def test_one_review_per_user_and_game(ana):
    assert review(ana, rating=8).status_code == 201
    again = review(ana, rating=9)
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "review_exists"
    assert review(ana, CELESTE, rating=9).status_code == 201


def test_edit_own_review_sets_updated_at(ana):
    rid = review(ana, rating=6, body="ok").get_json()["review"]["id"]
    response = ana.patch(f"/api/reviews/{rid}", {"rating": 9, "body": "Mudei de ideia."})
    assert response.status_code == 200
    data = response.get_json()["review"]
    assert (data["rating"], data["body"]) == (9, "Mudei de ideia.")
    assert data["updated_at"] is not None


def test_edit_only_rating_keeps_text_and_empty_text_clears_it(ana):
    rid = review(ana, rating=6, body="texto").get_json()["review"]["id"]
    kept = ana.patch(f"/api/reviews/{rid}", {"rating": 7}).get_json()["review"]
    assert kept["body"] == "texto"
    cleared = ana.patch(f"/api/reviews/{rid}", {"body": ""}).get_json()["review"]
    assert cleared["body"] is None and cleared["rating"] == 7


def test_edit_requires_something_valid(ana):
    rid = review(ana, rating=6).get_json()["review"]["id"]
    assert ana.patch(f"/api/reviews/{rid}", {}).status_code == 422
    assert ana.patch(f"/api/reviews/{rid}", {"rating": 6.2}).status_code == 422
    assert ana.get(f"/api/reviews/{rid}").get_json()["review"]["rating"] == 6


def test_cannot_edit_or_delete_someone_elses_review(ana, bruno):
    rid = review(ana, rating=8, body="minha").get_json()["review"]["id"]
    edit = bruno.patch(f"/api/reviews/{rid}", {"rating": 1, "body": "sabotagem"})
    assert edit.status_code == 403
    assert bruno.delete(f"/api/reviews/{rid}").status_code == 403
    stored = ana.get(f"/api/reviews/{rid}").get_json()["review"]
    assert (stored["rating"], stored["body"]) == (8, "minha")


def test_missing_review_is_404(ana):
    assert ana.patch("/api/reviews/9999", {"rating": 5}).status_code == 404
    assert ana.delete("/api/reviews/9999").status_code == 404
    assert ana.get("/api/reviews/9999").status_code == 404


def test_delete_removes_review_likes_and_activity(ana, bruno):
    rid = review(ana, rating=8, body="boa").get_json()["review"]["id"]
    bruno.put(f"/api/reviews/{rid}/like")
    assert ana.delete(f"/api/reviews/{rid}").status_code == 200
    assert ana.get(f"/api/reviews/{rid}").status_code == 404
    kinds = [item["type"] for item in ana.get("/api/users/ana/activity").get_json()["items"]]
    assert kinds == ["logged"]  # sobrou só o registro no diário; a atividade "avaliou" saiu com a review
    assert ana.get(f"/api/games/{HADES}").get_json()["community"]["count"] == 0


def test_community_average_is_computed_from_real_reviews(ana, bruno, make_user):
    carla = make_user("carla")
    review(ana, rating=8)
    review(bruno, rating=9, body="Ótimo.")
    review(carla, rating=7.5)
    community = ana.get(f"/api/games/{HADES}").get_json()["community"]
    assert community["count"] == 3
    assert community["average"] == round((8 + 9 + 7.5) / 3, 2)
    assert community["with_text"] == 1
    assert community["distribution"][7] == 1  # 7,5
    assert community["distribution"][8] == 1  # 8
    assert community["distribution"][9] == 1  # 9
    assert sum(community["distribution"]) == 3


def test_a_perfect_ten_lands_in_the_last_bucket(ana):
    review(ana, rating=10)
    assert ana.get(f"/api/games/{HADES}").get_json()["community"]["distribution"][9] == 1


def test_community_rating_is_kept_separate_from_rawg_data(ana):
    body = ana.get(f"/api/games/{HADES}").get_json()
    assert body["community"]["average"] is None and body["community"]["count"] == 0
    assert "rawg_rating" in body["game"]  # nota agregada pela RAWG, em outro campo
    review(ana, rating=4)
    after = ana.get(f"/api/games/{HADES}").get_json()
    assert after["community"]["average"] == 4
    assert after["game"]["rawg_rating"] == body["game"]["rawg_rating"]


def test_game_review_list_shows_only_reviews_with_text_and_sorts(ana, bruno, make_user):
    carla = make_user("carla")
    review(ana, rating=5)  # sem texto: entra na média, não na lista
    review(bruno, rating=9, body="Adorei")
    review(carla, rating=3, body="Não gostei")
    texts = ana.get(f"/api/games/{HADES}/reviews").get_json()["items"]
    assert {r["user"]["username"] for r in texts} == {"bruno", "carla"}
    highest = ana.get(f"/api/games/{HADES}/reviews?sort=highest").get_json()["items"]
    assert [r["rating"] for r in highest] == [9, 3]
    lowest = ana.get(f"/api/games/{HADES}/reviews?sort=lowest").get_json()["items"]
    assert [r["rating"] for r in lowest] == [3, 9]
    assert ana.get(f"/api/games/{HADES}/reviews?sort=aleatorio").status_code == 400
    assert ana.get(f"/api/games/{HADES}").get_json()["community"]["count"] == 3


def test_review_list_for_game_with_no_local_record_is_empty(api):
    body = api.get(f"/api/games/{fake_rawg.by_name('Balatro')['id']}/reviews").get_json()
    assert body["items"] == [] and body["has_next"] is False


def test_recent_reviews_feed_and_user_reviews(ana, bruno):
    review(ana, rating=8, body="primeira")
    review(ana, CELESTE, rating=9)
    review(bruno, rating=7, body="segunda")
    recent = ana.get("/api/reviews").get_json()["items"]
    assert [r["body"] for r in recent] == ["segunda", "primeira"]  # sem texto não aparece
    mine = ana.get("/api/users/ana/reviews").get_json()["items"]
    assert len(mine) == 2


def test_like_and_unlike(ana, bruno):
    rid = review(ana, rating=8, body="boa").get_json()["review"]["id"]
    liked = bruno.put(f"/api/reviews/{rid}/like")
    assert liked.status_code == 200
    assert liked.get_json() == {"liked": True, "like_count": 1}
    assert bruno.get(f"/api/reviews/{rid}").get_json()["review"]["liked"] is True
    assert ana.get(f"/api/reviews/{rid}").get_json()["review"]["liked"] is False
    assert bruno.delete(f"/api/reviews/{rid}/like").get_json() == {"liked": False, "like_count": 0}


def test_duplicate_likes_are_idempotent(ana, bruno):
    rid = review(ana, rating=8, body="boa").get_json()["review"]["id"]
    for _ in range(3):
        assert bruno.put(f"/api/reviews/{rid}/like").get_json()["like_count"] == 1
    assert bruno.delete(f"/api/reviews/{rid}/like").get_json()["like_count"] == 0
    assert bruno.delete(f"/api/reviews/{rid}/like").get_json()["like_count"] == 0


def test_like_count_sums_distinct_users(ana, bruno, make_user):
    carla = make_user("carla")
    rid = review(ana, rating=8, body="boa").get_json()["review"]["id"]
    bruno.put(f"/api/reviews/{rid}/like")
    carla.put(f"/api/reviews/{rid}/like")
    assert ana.get(f"/api/reviews/{rid}").get_json()["review"]["like_count"] == 2


def test_cannot_like_own_review_or_missing_review(ana):
    rid = review(ana, rating=8, body="boa").get_json()["review"]["id"]
    own = ana.put(f"/api/reviews/{rid}/like")
    assert own.status_code == 400 and own.get_json()["error"]["code"] == "cannot_like_own"
    assert ana.put("/api/reviews/9999/like").status_code == 404


def test_review_on_unknown_game_fails_cleanly(ana):
    response = ana.post("/api/games/123456789/reviews", {"rating": 5})
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "game_not_found"
