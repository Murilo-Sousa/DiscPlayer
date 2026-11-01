"""Retrospectiva do ano de uma pessoa: tudo calculado dos registros reais dela.

Nada aqui é inventado nem estimado. O que entra:

  * jogos ZERADOS no ano, pela data de término (a jogada atual e as jogadas anteriores:
    zerar o mesmo jogo duas vezes no ano conta duas vezes);
  * jogos COMEÇADOS no ano, pela data de início;
  * jogos ABANDONADOS e RECOMEÇOS ("jogar de novo") no ano, pelo histórico do diário;
  * notas dadas no ano (pela data em que a review foi publicada) e as curtidas recebidas;
  * o "jogo do ano": entre os zerados do ano, o de maior nota da própria pessoa (em caso de
    empate, o zerado mais recentemente; sem nenhuma nota maior que zero, não há jogo do ano);
  * o ritmo: mais rápido e mais longo, só quando há pelo menos dois zerados com as duas datas.

O app não guarda gêneros nem horas jogadas, então a retrospectiva não os mostra.

Datas de calendário (início e término) são as do fuso de quem joga. Já as reviews e o histórico
do diário têm hora em UTC; algo feito bem na virada do ano pode cair no ano vizinho.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from ..db import fetch_all, fetch_one
from ..errors import ApiError
from ..serializers import game_from_row
from ..utils.dates import parse_iso_date, today_utc
from ..utils.ratings import distribution_from
from . import profiles

MIN_YEAR = 2000
COMPLETED_LIST_SIZE = 12


def is_valid_year(year: int) -> bool:
    """De 2000 até o ano que vem (um dia à frente de UTC já pode ser o ano seguinte em alguns fusos)."""
    return MIN_YEAR <= year <= today_utc().year + 1


def require_valid_year(year: int) -> int:
    if not is_valid_year(year):
        raise ApiError(404, "not_found", "Não há retrospectiva para este ano.")
    return year


def _bounds(year: int) -> dict:
    return {
        "a": f"{year}-01-01",  # datas de calendário: BETWEEN :a AND :b
        "b": f"{year}-12-31",
        "ts_a": f"{year}-01-01",  # horários ISO em UTC: >= :ts_a AND < :ts_b
        "ts_b": f"{year + 1}-01-01",
    }


def years_with_data(user_id: int) -> list[int]:
    """Anos em que a pessoa tem algo para mostrar, do mais recente ao mais antigo."""
    rows = fetch_all(
        """
        SELECT DISTINCT y FROM (
            SELECT substr(completed_at, 1, 4) AS y FROM library_entries WHERE user_id = :u AND status = 'zerado'
            UNION ALL SELECT substr(started_at, 1, 4) FROM library_entries WHERE user_id = :u
            UNION ALL SELECT substr(completed_at, 1, 4) FROM playthroughs WHERE user_id = :u AND status = 'zerado'
            UNION ALL SELECT substr(started_at, 1, 4) FROM playthroughs WHERE user_id = :u
            UNION ALL SELECT substr(created_at, 1, 4) FROM reviews WHERE user_id = :u
            UNION ALL SELECT substr(created_at, 1, 4) FROM activities
                       WHERE user_id = :u AND type = 'logged' AND (status = 'abandonado' OR is_replay = 1)
        ) WHERE y IS NOT NULL
        """,
        {"u": user_id},
    )
    years = {int(r["y"]) for r in rows if r["y"] and r["y"].isdigit()}
    return sorted((y for y in years if is_valid_year(y)), reverse=True)


def default_year(user_id: int) -> int:
    """O ano mais recente com dados; sem nenhum, o ano atual."""
    years = years_with_data(user_id)
    return years[0] if years else today_utc().year


def _completions(user_id: int, year: int) -> list[sqlite3.Row]:
    """Cada conclusão do ano (jogada atual e anteriores), com o jogo e a nota da própria pessoa."""
    return fetch_all(
        """
        SELECT g.rawg_id, g.name AS game_name, g.slug AS game_slug, g.cover_url, g.release_date,
               c.started_at, c.completed_at,
               (SELECT rv.rating FROM reviews rv WHERE rv.user_id = :u AND rv.game_id = c.game_id) AS rating
          FROM (
              SELECT game_id, started_at, completed_at FROM library_entries
               WHERE user_id = :u AND status = 'zerado' AND completed_at BETWEEN :a AND :b
              UNION ALL
              SELECT game_id, started_at, completed_at FROM playthroughs
               WHERE user_id = :u AND status = 'zerado' AND completed_at BETWEEN :a AND :b
          ) c JOIN games g ON g.id = c.game_id
        """,
        {"u": user_id, **_bounds(year)},
    )


def _days(started: str | None, completed: str | None) -> int | None:
    first, last = parse_iso_date(started), parse_iso_date(completed)
    if first is None or last is None or last < first:
        return None
    return (last - first).days


def _group_games(completions: list[sqlite3.Row]) -> list[dict]:
    """Um item por jogo (zerar duas vezes vira `times: 2`), do mais bem avaliado ao menos."""
    by_game: dict[int, dict] = {}
    for row in completions:
        item = by_game.get(row["rawg_id"])
        if item is None:
            item = by_game[row["rawg_id"]] = {
                "game": game_from_row(row),
                "rating": row["rating"],
                "completed_at": row["completed_at"],
                "times": 0,
                "days": None,
            }
        item["times"] += 1
        if row["completed_at"] >= item["completed_at"]:  # a conclusão mais recente do jogo manda
            item["completed_at"] = row["completed_at"]
            item["days"] = _days(row["started_at"], row["completed_at"])
    return sorted(
        by_game.values(),
        key=lambda i: (i["rating"] is None, -(i["rating"] or 0), _neg_date(i["completed_at"]), i["game"]["name"].lower()),
    )


def _neg_date(value: str) -> int:
    """Chave para ordenar datas da mais recente para a mais antiga (AAAA-MM-DD vira um inteiro negativo)."""
    parsed = parse_iso_date(value) or date.min
    return -parsed.toordinal()


def _pace(completions: list[sqlite3.Row]) -> dict | None:
    timed = []
    for row in completions:
        days = _days(row["started_at"], row["completed_at"])
        if days is not None:
            timed.append((days, row))
    if len(timed) < 2:  # com um só, "mais rápido" e "mais longo" seriam o mesmo jogo
        return None

    def pick(entry: tuple[int, sqlite3.Row]) -> dict:
        return {"game": game_from_row(entry[1]), "days": entry[0], "completed_at": entry[1]["completed_at"]}

    fastest = min(timed, key=lambda t: (t[0], t[1]["completed_at"], t[1]["game_name"].lower()))
    longest = max(timed, key=lambda t: (t[0], t[1]["completed_at"], t[1]["game_name"].lower()))
    average = sum(days for days, _ in timed) / len(timed)
    return {"average_days": round(average, 1), "fastest": pick(fastest), "longest": pick(longest)}


def _ratings(user_id: int, year: int) -> dict:
    bounds = _bounds(year)
    buckets = distribution_from(
        fetch_all(
            "SELECT CAST(rating AS INTEGER) AS bucket, COUNT(*) AS n FROM reviews"
            " WHERE user_id = :u AND created_at >= :ts_a AND created_at < :ts_b GROUP BY bucket",
            {"u": user_id, **bounds},
        )
    )
    totals = fetch_one(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg, COALESCE(SUM(body IS NOT NULL), 0) AS with_text FROM reviews"
        " WHERE user_id = :u AND created_at >= :ts_a AND created_at < :ts_b",
        {"u": user_id, **bounds},
    )
    return {
        "count": totals["n"],
        "average": round(totals["avg"], 2) if totals["avg"] is not None else None,
        "with_text": totals["with_text"],
        "distribution": buckets,
    }


def _count(sql: str, user_id: int, year: int) -> int:
    return fetch_one(sql, {"u": user_id, **_bounds(year)})["n"]


def build(user: sqlite3.Row, year: int) -> dict:
    """A retrospectiva de `user` em `year` (já validado por quem chama)."""
    user_id = user["id"]
    completions = _completions(user_id, year)
    games = _group_games(completions)
    by_month = profiles.completions_by_month(user_id, year)

    started = _count(
        "SELECT (SELECT COUNT(*) FROM library_entries WHERE user_id = :u AND started_at BETWEEN :a AND :b)"
        " + (SELECT COUNT(*) FROM playthroughs WHERE user_id = :u AND started_at BETWEEN :a AND :b) AS n",
        user_id,
        year,
    )
    abandoned = _count(
        "SELECT COUNT(DISTINCT game_id) AS n FROM activities WHERE user_id = :u AND type = 'logged'"
        " AND status = 'abandonado' AND created_at >= :ts_a AND created_at < :ts_b",
        user_id,
        year,
    )
    replays = _count(
        "SELECT COUNT(*) AS n FROM activities WHERE user_id = :u AND type = 'logged' AND is_replay = 1"
        " AND created_at >= :ts_a AND created_at < :ts_b",
        user_id,
        year,
    )
    ratings = _ratings(user_id, year)

    busiest = None
    if any(by_month):
        busiest = by_month.index(max(by_month)) + 1  # empate: o mês mais cedo

    # Nota 0 não escolhe "jogo do ano": se o melhor do ano ficou com 0, ele não é destaque de nada.
    best = games[0] if games and (games[0]["rating"] or 0) > 0 else None
    has_data = bool(completions or started or abandoned or replays or ratings["count"])

    return {
        "user": {
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar_url": user["avatar_url"],
            "is_demo": bool(user["is_demo"]),
        },
        "year": year,
        "partial": year == today_utc().year,
        "years": years_with_data(user_id),
        "empty": not has_data,
        "totals": {
            "completed": len(completions),
            "completed_games": len(games),
            "started": started,
            "abandoned": abandoned,
            "replays": replays,
        },
        "by_month": by_month,
        "busiest_month": busiest,
        "game_of_the_year": best,
        "completed_games": games[:COMPLETED_LIST_SIZE],
        "pace": _pace(completions),
        "ratings": ratings,
        "social": {
            "likes_received": _count(
                "SELECT COUNT(*) AS n FROM review_likes rl JOIN reviews r ON r.id = rl.review_id"
                " WHERE r.user_id = :u AND rl.created_at >= :ts_a AND rl.created_at < :ts_b",
                user_id,
                year,
            ),
            "new_followers": _count(
                "SELECT COUNT(*) AS n FROM follows WHERE followed_id = :u"
                " AND created_at >= :ts_a AND created_at < :ts_b",
                user_id,
                year,
            ),
            # Só listas públicas: o número aparece numa página pública e não revela listas privadas.
            "lists_created": _count(
                "SELECT COUNT(*) AS n FROM lists WHERE user_id = :u AND is_public = 1"
                " AND created_at >= :ts_a AND created_at < :ts_b",
                user_id,
                year,
            ),
        },
    }
