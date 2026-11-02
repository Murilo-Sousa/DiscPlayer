"""O início de quem está logado: quem joga o quê agora e as novidades da comunidade, já agrupadas.

O feed de atividades é um registro de eventos (uma linha por ação). Para o início isso é ruído: quem zerou e
avaliou o mesmo jogo aparece duas vezes, e "quer jogar" parece novidade. Aqui os eventos viram cartões:

  * "zerou" + "avaliou" do mesmo jogo, pela mesma pessoa, viram um cartão só (com a nota e o trecho da review);
  * vários "quer jogar" seguidos da mesma pessoa viram "guardou N jogos na fila";
  * criar uma lista vira um cartão com as capas (só lista pública e com algum jogo);
  * abandonar e pausar ficam como linhas simples;
  * começar a jogar e jogar de novo não entram: quem joga o quê agora é o "jogando agora".

Nada é inventado: tudo sai do diário, das reviews e das listas reais, e a atividade de quem está vendo fica de fora.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db import fetch_all, fetch_one
from ..serializers import activity_from_row, game_from_row, user_public
from . import feed as feed_service
from . import lists as lists_service

SCOPES = ("following", "community")
RAW_WINDOW = 150  # quantas atividades recentes entram no agrupamento
MERGE_WINDOW = timedelta(days=3)  # "zerou" e "avaliou" do mesmo jogo, até este intervalo, viram um cartão
QUEUE_WINDOW = timedelta(hours=12)  # "quer jogar" seguidos dentro deste intervalo viram um cartão
QUEUE_GAMES_SHOWN = 4
PLAYING_ROWS = 300


def following_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM follows WHERE follower_id = ?", (user_id,))["n"]


# ----------------------------------------------------------------------------- jogando agora
def playing_now(viewer_id: int, scope: str, limit: int = 12) -> dict:
    """Um cartão por pessoa: o jogo que ela começou há menos tempo (e quantos outros joga), do mais recente ao mais antigo.

    Fora quem está vendo. Em `following`, só quem ele segue; em `community`, todo mundo.
    """
    only_followed = " AND e.user_id IN (SELECT followed_id FROM follows WHERE follower_id = :viewer)" if scope == "following" else ""
    rows = fetch_all(
        "SELECT u.id AS user_id, u.username, u.display_name, u.avatar_url, u.is_demo,"
        " g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,"
        " e.started_at, COALESCE(e.status_changed_at, e.updated_at) AS since"
        " FROM library_entries e JOIN users u ON u.id = e.user_id JOIN games g ON g.id = e.game_id"
        f" WHERE e.status = 'jogando' AND e.user_id <> :viewer{only_followed}"
        " ORDER BY since DESC, e.id DESC LIMIT :rows",
        {"viewer": viewer_id, "rows": PLAYING_ROWS},
    )
    people: dict[int, dict] = {}
    for row in rows:
        card = people.get(row["user_id"])
        if card is None:
            people[row["user_id"]] = {
                "user": user_public(row),
                "game": game_from_row(row),
                "started_at": row["started_at"],
                "since": row["since"],
                "also": 0,
            }
        else:
            card["also"] += 1
    items = list(people.values())
    return {"scope": scope, "items": items[:limit], "total": len(items), "following": following_count(viewer_id)}


# ----------------------------------------------------------------------------- novidades
def _when(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _review_part(activity: dict | None) -> dict:
    review = (activity or {}).get("review") or {}
    return {
        "rating": review.get("rating"),
        "excerpt": review.get("excerpt"),
        "has_spoilers": bool(review.get("has_spoilers")),
        "like_count": review.get("like_count", 0),
    }


def group(activities: list[dict], limit: int) -> list[dict]:
    """Agrupa atividades (da mais nova para a mais antiga) em cartões; cada cartão fica onde está a sua atividade mais nova."""
    finishes: dict[tuple, list[dict]] = {}
    reviews: dict[tuple, list[dict]] = {}
    for activity in activities:
        if activity["type"] == "reviewed":
            reviews.setdefault((activity["user"]["username"], activity["game"]["rawg_id"]), []).append(activity)
        elif activity["type"] == "logged" and activity["status"] == "zerado":
            finishes.setdefault((activity["user"]["username"], activity["game"]["rawg_id"]), []).append(activity)

    used: set[int] = set()

    def partner(pool: dict, activity: dict) -> dict | None:
        key = (activity["user"]["username"], activity["game"]["rawg_id"])
        for other in pool.get(key, []):
            if other["id"] not in used and abs(_when(other["created_at"]) - _when(activity["created_at"])) <= MERGE_WINDOW:
                return other
        return None

    cards: list[dict] = []
    open_queue: dict[str, dict] = {}
    for activity in activities:
        if activity["id"] in used:
            continue
        used.add(activity["id"])
        kind, user = activity["type"], activity["user"]
        base = {"user": user, "created_at": activity["created_at"]}
        if kind == "reviewed":
            finish = partner(finishes, activity)
            if finish:
                used.add(finish["id"])
            cards.append({**base, "kind": "finished" if finish else "reviewed", "game": activity["game"], **_review_part(activity)})
        elif kind == "logged":
            status = activity["status"]
            if status == "zerado":
                review = partner(reviews, activity)
                if review:
                    used.add(review["id"])
                cards.append({**base, "kind": "finished", "game": activity["game"], **_review_part(review)})
            elif status in ("abandonado", "pausado"):
                cards.append({**base, "kind": "status", "status": status, "game": activity["game"]})
            elif status == "quero_jogar":
                current = open_queue.get(user["username"])
                game_id = activity["game"]["rawg_id"]
                if current and _when(current["_oldest"]) - _when(activity["created_at"]) <= QUEUE_WINDOW:
                    current["_oldest"] = activity["created_at"]
                    if game_id not in current["_ids"]:  # o mesmo jogo guardado duas vezes conta uma
                        current["_ids"].add(game_id)
                        current["count"] += 1
                        if len(current["games"]) < QUEUE_GAMES_SHOWN:
                            current["games"].append(activity["game"])
                else:
                    card = {
                        **base,
                        "kind": "queued",
                        "games": [activity["game"]],
                        "count": 1,
                        "_oldest": activity["created_at"],
                        "_ids": {game_id},
                    }
                    open_queue[user["username"]] = card
                    cards.append(card)
            # "jogando" e "voltou a jogar" ficam de fora: quem joga o quê agora está no "jogando agora"
        elif kind == "list_created":
            cards.append({**base, "kind": "list", "list": activity["list"]})
    cards = _with_lists(cards)
    for card in cards:
        card.pop("_oldest", None)
        card.pop("_ids", None)
    return cards[:limit]


def _with_lists(cards: list[dict]) -> list[dict]:
    """Completa os cartões de lista (número de jogos e capas) e tira os de lista vazia."""
    ids = [card["list"]["id"] for card in cards if card["kind"] == "list"]
    if not ids:
        return cards
    counts = {
        row["id"]: row["n"]
        for row in fetch_all(
            f"SELECT l.id, (SELECT COUNT(*) FROM list_games lg WHERE lg.list_id = l.id) AS n FROM lists l"
            f" WHERE l.id IN ({','.join('?' * len(ids))})",
            tuple(ids),
        )
    }
    covers = lists_service.covers_for(ids)
    kept = []
    for card in cards:
        if card["kind"] == "list":
            total = counts.get(card["list"]["id"], 0)
            if total == 0:
                continue
            card = {**card, "list": {**card["list"], "game_count": total, "covers": covers.get(card["list"]["id"], [])}}
        kept.append(card)
    return kept


def highlights(viewer_id: int, scope: str, limit: int = 10) -> dict:
    rows = feed_service.activities(
        "following" if scope == "following" else "global",
        viewer_id=viewer_id,
        limit=RAW_WINDOW,
        skip_own=True,
    )
    cards = group([activity_from_row(row) for row in rows], limit)
    return {"scope": scope, "items": cards, "following": following_count(viewer_id)}
