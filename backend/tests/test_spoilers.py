"""Aviso de spoilers nas reviews: marcação, edição e vazamento em feed e busca."""
from __future__ import annotations

from .conftest import CELESTE, HADES

SECRET = "No final o protagonista descobre que o mentor era o vilão."


def review(client, rawg_id=HADES, **body):
    return client.post(f"/api/games/{rawg_id}/reviews", body)


def test_reviews_are_spoiler_free_by_default(ana):
    data = review(ana, rating=8, body="Muito bom.").get_json()["review"]
    assert data["has_spoilers"] is False


def test_review_can_be_published_with_a_spoiler_warning(ana):
    data = review(ana, rating=9, body=SECRET, has_spoilers=True).get_json()["review"]
    assert data["has_spoilers"] is True and data["body"] == SECRET
    # a mesma informação volta em todas as listagens
    assert ana.get(f"/api/games/{HADES}/reviews").get_json()["items"][0]["has_spoilers"] is True
    assert ana.get("/api/users/ana/reviews").get_json()["items"][0]["has_spoilers"] is True
    assert ana.get("/api/reviews").get_json()["items"][0]["has_spoilers"] is True
    detail = ana.get(f"/api/games/{HADES}").get_json()
    assert detail["reviews"][0]["has_spoilers"] is True and detail["viewer"]["review"]["has_spoilers"] is True


def test_spoiler_flag_must_be_a_boolean(ana):
    for bad in ["sim", 1, "true", None, []]:
        response = review(ana, rating=8, body="Texto", has_spoilers=bad)
        assert response.status_code == 422, bad
        assert "has_spoilers" in response.get_json()["error"]["fields"]
    assert ana.get("/api/users/ana/reviews").get_json()["items"] == []


def test_flag_without_text_is_not_kept(ana):
    # Sem texto não há o que esconder: o aviso não fica marcado.
    assert review(ana, rating=8, has_spoilers=True).get_json()["review"]["has_spoilers"] is False


def test_flag_can_be_changed_on_edit_and_cleared_with_the_text(ana):
    created = review(ana, rating=8, body=SECRET).get_json()["review"]
    url = f"/api/reviews/{created['id']}"

    only_flag = ana.patch(url, {"has_spoilers": True}).get_json()["review"]
    assert only_flag["has_spoilers"] is True and only_flag["body"] == SECRET and only_flag["rating"] == 8

    text_edit = ana.patch(url, {"body": SECRET + " Chorei."}).get_json()["review"]
    assert text_edit["has_spoilers"] is True  # editar o texto não tira o aviso

    off = ana.patch(url, {"has_spoilers": False}).get_json()["review"]
    assert off["has_spoilers"] is False

    ana.patch(url, {"has_spoilers": True})
    cleared = ana.patch(url, {"body": None}).get_json()["review"]
    assert cleared["body"] is None and cleared["has_spoilers"] is False
    again = ana.patch(url, {"has_spoilers": True}).get_json()["review"]  # sem texto: continua desmarcado
    assert again["has_spoilers"] is False


def test_patch_with_no_fields_still_asks_for_something(ana):
    created = review(ana, rating=8, body="Oi").get_json()["review"]
    response = ana.patch(f"/api/reviews/{created['id']}", {})
    assert response.status_code == 422


def test_other_people_cannot_change_the_flag(ana, bruno):
    created = review(ana, rating=8, body=SECRET).get_json()["review"]
    assert bruno.patch(f"/api/reviews/{created['id']}", {"has_spoilers": True}).status_code == 403
    assert bruno.get(f"/api/reviews/{created['id']}").get_json()["review"]["has_spoilers"] is False


def test_feed_never_shows_text_from_a_review_with_spoilers(ana, bruno):
    bruno.put("/api/users/ana/follow")
    review(ana, HADES, rating=9, body=SECRET, has_spoilers=True)
    review(ana, CELESTE, rating=8, body="Trilha sonora linda.")
    for payload in (
        ana.get("/api/users/ana/activity").get_json(),
        bruno.get("/api/feed").get_json(),
        bruno.get("/api/activity").get_json(),
    ):
        reviewed = {a["game"]["name"]: a["review"] for a in payload["items"] if a["type"] == "reviewed"}
        assert reviewed["Hades"]["has_spoilers"] is True
        assert reviewed["Hades"]["excerpt"] is None and reviewed["Hades"]["rating"] == 9
        assert reviewed["Celeste"]["has_spoilers"] is False
        assert reviewed["Celeste"]["excerpt"] == "Trilha sonora linda."
        assert "mentor" not in str(payload)


def test_search_does_not_match_or_return_text_from_reviews_with_spoilers(ana, bruno):
    review(ana, HADES, rating=9, body=SECRET, has_spoilers=True)
    review(ana, CELESTE, rating=8, body="O mentor aparece cedo e ajuda muito.")
    hits = bruno.get("/api/search?q=mentor").get_json()["reviews"]
    assert [h["game"]["name"] for h in hits] == ["Celeste"]
    assert "vilão" not in str(hits)


def test_spoiler_review_still_counts_in_stats_and_community_average(ana, bruno):
    review(ana, HADES, rating=10, body=SECRET, has_spoilers=True)
    review(bruno, HADES, rating=6, body="Ok.")
    community = ana.get(f"/api/games/{HADES}").get_json()["community"]
    assert community["average"] == 8 and community["count"] == 2 and community["with_text"] == 2
