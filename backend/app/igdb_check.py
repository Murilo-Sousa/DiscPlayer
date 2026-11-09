"""Confere a integração com o IGDB de verdade, uma etapa de cada vez, e conta o que encontrou.

    python -m app.igdb_check                 (com IGDB_CLIENT_ID e IGDB_CLIENT_SECRET no backend/.env)
    python -m app.igdb_check --sem-imagens   (não tenta baixar capas)

Para que serve: o DiscPlayer foi escrito seguindo a documentação do IGDB, e o IGDB muda (campos antigos saem, campos
novos entram). Este comando chama o serviço com as suas credenciais e confere, num relatório curto, se cada coisa
de que o site depende ainda funciona: login na Twitch, gêneros, plataformas, listas, busca, filtros, ordens, página
do jogo, classificações etárias, filtro de conteúdo adulto e imagens.

Segurança: o relatório nunca mostra o Client ID, o Client Secret nem o token (e qualquer trecho parecido com eles é
trocado por ***). Pode copiar a saída inteira e colar numa conversa. Os nomes de jogos adultos também não aparecem:
só as contagens.

Código de saída: 0 se nada falhou (avisos não contam), 1 se alguma conferência falhou, 2 se faltam as credenciais.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date
from typing import Callable

import requests
from flask import current_app

from .services import adult, igdb
from .services.igdb import IgdbError, Query

_ADULT_THEME_ID = 42  # no IGDB, o tema "Erotic"
_SAMPLE = 40


class Report:
    """Escreve as linhas do relatório e conta o que deu certo, o que merece atenção e o que falhou."""

    def __init__(self, out: Callable[[str], None] = print, secrets: tuple[str, ...] = ()):
        self._out = out
        self._secrets = tuple(s for s in secrets if s and len(s) >= 4)
        self.ok_count = self.warn_count = self.fail_count = 0

    def _say(self, text: str) -> None:
        for secret in self._secrets:
            text = text.replace(secret, "***")
        self._out(text)

    def title(self, text: str) -> None:
        self._say(f"\n{text}")

    def ok(self, text: str) -> None:
        self.ok_count += 1
        self._say(f"  ✔ {text}")

    def warn(self, text: str) -> None:
        self.warn_count += 1
        self._say(f"  ⚠ {text}")

    def fail(self, text: str) -> None:
        self.fail_count += 1
        self._say(f"  ✖ {text}")

    def info(self, text: str) -> None:
        self._say(f"    {text}")


def _explain(exc: Exception) -> str:
    if isinstance(exc, IgdbError):
        extra = f" (o IGDB disse: {exc.detail})" if exc.detail else ""
        return f"{exc.message}{extra}"
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _step(report: Report, title: str, check: Callable[[], None]) -> None:
    """Roda uma etapa. Um erro vira uma linha de falha, nunca interrompe as outras."""
    report.title(title)
    try:
        check()
    except Exception as exc:  # noqa: BLE001 — o relatório existe justamente para mostrar o que quebrou
        report.fail(_explain(exc))


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ------------------------------------------------------------------------------------------------------ as etapas
def _token(report: Report) -> None:
    igdb.clear_token()
    igdb._access_token(force=True)
    days = max(0.0, (igdb._token["expires_at"] - time.monotonic() + 300) / 86400)
    report.ok(f"a Twitch aceitou as credenciais (o token vale por cerca de {days:.0f} dias)")


def _genres(report: Report) -> None:
    genres = igdb.list_genres()
    if not genres:
        report.fail("o IGDB não devolveu nenhum gênero")
        return
    report.ok(f"{_plural(len(genres), 'gênero', 'gêneros')}: {', '.join(g['name'] for g in genres[:8])}…")
    slugs = {g["slug"] for g in genres}
    untranslated = sorted(slugs - set(igdb.GENRE_NAMES))
    missing = sorted(set(igdb.GENRE_NAMES) - slugs)
    if untranslated:
        report.warn("gêneros que aparecem com o nome em inglês (sem tradução): " + ", ".join(untranslated))
    if missing:
        report.warn("gêneros que esperávamos e o IGDB não tem mais: " + ", ".join(missing))
    if not untranslated and not missing:
        report.ok("todos os gêneros têm tradução e todos os nomes esperados existem")


def _platforms(report: Report) -> None:
    wanted = sorted({pid for group in igdb.PLATFORM_GROUPS for pid in group["igdb_ids"]})
    rows = igdb.fetch_json(Query("platforms", ("name",), (("id", "in", tuple(wanted)),), limit=500))
    names = {row["id"]: row.get("name", "?") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), int)}
    for group in igdb.PLATFORM_GROUPS:
        found = [names[pid] for pid in group["igdb_ids"] if pid in names]
        lost = [str(pid) for pid in group["igdb_ids"] if pid not in names]
        line = f"{group['name']}: {', '.join(found) or 'nenhuma'}"
        (report.warn if lost else report.ok)(line + (f"  (números sem plataforma no IGDB: {', '.join(lost)})" if lost else ""))
    report.info("Confira se cada nome pertence mesmo ao grupo em que está.")


def _lists(report: Report) -> None:
    today = date.today().isoformat()
    for kind, label in (("popular", "Em alta"), ("new", "Lançamentos")):
        data = igdb.featured_games(kind)
        results = data["results"]
        if not results:
            report.fail(f"{label}: a lista veio vazia")
            continue
        report.ok(f"{label}: {_plural(len(results), 'jogo', 'jogos')} (de {data['count']}); o primeiro é {results[0]['name']}")
        if sum(1 for g in results if g["cover_thumb_url"]) < len(results):
            report.warn(f"{label}: há jogos sem capa na lista")
        if kind == "new" and any((g["released"] or "") > today for g in results):
            report.fail("Lançamentos: há jogo com data no futuro")
        if kind == "popular" and any(not g["genres"] for g in results[:5]):
            report.warn("Em alta: há jogos sem gênero entre os primeiros")


def _search(report: Report) -> None:
    found = igdb.search_games(search="zelda", page_size=8)
    if not found["results"]:
        report.fail("a busca por “zelda” não devolveu nada")
        return
    report.ok(f"busca por “zelda”: {_plural(len(found['results']), 'jogo', 'jogos')} na página, {found['count']} no total")
    report.info("os primeiros: " + "; ".join(g["name"] for g in found["results"][:4]))
    total = igdb.fetch_json(Query("games", filters=igdb._MAIN_GAMES, search="zelda", count=True))
    if isinstance(total, dict) and isinstance(total.get("count"), int):
        report.ok(f"a contagem junto com a busca funciona ({total['count']} jogos principais)")
    else:
        report.fail(f"a contagem junto com a busca veio num formato inesperado: {str(total)[:120]}")
    ordered = igdb.search_games(search="zelda", ordering="released", page_size=8)["results"]
    dates = [g["released"] for g in ordered if g["released"]]
    if ordered and dates == sorted(dates, reverse=True):
        report.ok("busca com ordem própria (lançamento mais recente) funciona")
    else:
        report.fail("a busca ordenada por lançamento não veio em ordem")
    try:
        igdb.fetch_json(Query("games", ("name",), igdb._MAIN_GAMES, "zelda", "first_release_date desc", 3))
        report.info("O IGDB aceita `sort` junto com `search`: dá para ordenar a busca no servidor (hoje ordenamos aqui).")
    except IgdbError:
        report.info("O IGDB não aceita `sort` junto com `search`, como o DiscPlayer já presume (a ordem da busca é local).")


def _filters(report: Report) -> None:
    rpg = igdb.search_games(genres="role-playing-rpg", page_size=8)
    (report.ok if rpg["results"] else report.fail)(f"filtro de gênero (RPG): {rpg['count']} jogos")
    if rpg["results"] and not all("RPG" in g["genres"] for g in rpg["results"]):
        report.warn("filtro de gênero: algum resultado não traz o gênero RPG na lista")
    for group in igdb.PLATFORM_GROUPS[:4]:
        data = igdb.search_games(platforms=str(group["id"]), page_size=8)
        if not data["results"]:
            report.fail(f"filtro de plataforma ({group['name']}): nada")
        elif not all(group["name"] in g["platforms"] for g in data["results"]):
            report.fail(f"filtro de plataforma ({group['name']}): veio jogo de outra plataforma")
        else:
            report.ok(f"filtro de plataforma ({group['name']}): {data['count']} jogos")
    first = igdb.featured_games("popular")["results"]
    year = int(first[0]["released"][:4]) if first and first[0]["released"] else date.today().year - 1
    in_year = igdb.search_games(year=year, page_size=8)
    if not in_year["results"]:
        report.fail(f"filtro de ano ({year}): nada")
    elif not all((g["released"] or "").startswith(str(year)) for g in in_year["results"]):
        report.fail(f"filtro de ano ({year}): veio jogo de outro ano")
    else:
        report.ok(f"filtro de ano ({year}): {in_year['count']} jogos")
    for ordering in (o for o in igdb.ORDERINGS if o != "relevance"):  # (a relevância é a ordem da busca, já conferida)
        data = igdb.search_games(ordering=ordering, page_size=8)["results"]
        if not data:
            report.fail(f"ordem “{ordering}”: nada")
            continue
        if ordering == "name":
            names = [g["name"].lower() for g in data]
            (report.ok if names == sorted(names) else report.info)(f"ordem “name”: {', '.join(g['name'] for g in data[:3])}… (símbolos e números vêm primeiro, na ordem do IGDB)")
        else:
            report.ok(f"ordem “{ordering}”: {', '.join(g['name'] for g in data[:3])}…")
    combined = igdb.search_games(genres="role-playing-rpg", platforms="2", year=year, page_size=4)
    report.ok(f"filtros combinados (RPG + PlayStation + {year}): {combined['count']} jogos")


def _detail(report: Report) -> None:
    candidates = igdb.featured_games("popular")["results"][:6]
    if not candidates:
        report.fail("sem jogos em alta para abrir a página de um deles")
        return
    for candidate in candidates:
        try:
            game = igdb.get_game(candidate["igdb_id"])
            break
        except igdb.IgdbBlocked:
            report.info(f"{candidate['name']} está escondido pelo filtro de conteúdo adulto; tentando o próximo.")
    else:
        report.warn("os primeiros jogos em alta estão todos escondidos pelo filtro; não deu para conferir a página")
        return
    report.ok(f"página de “{game['name']}” (IGDB {game['igdb_id']}) abriu")
    checks = [
        ("descrição", bool(game["description"]), f"{len(game['description'])} caracteres (em inglês, vem do IGDB)"),
        ("desenvolvedoras", bool(game["developers"]), ", ".join(game["developers"][:3])),
        ("publicadoras", bool(game["publishers"]), ", ".join(game["publishers"][:3])),
        ("plataformas", bool(game["platforms"]), f"{len(game['platforms'])} no total"),
        ("capa", bool(game["cover_url"]), game["cover_url"] or ""),
        ("imagem grande do topo", bool(game["cover_additional_url"]), (game["cover_additional_url"] or "").rsplit("/", 2)[-2] + "/" + (game["cover_additional_url"] or "").rsplit("/", 1)[-1]),
        ("capturas de tela", bool(game["screenshots"]), f"{len(game['screenshots'])}"),
        ("nota dos jogadores", game["igdb_rating"] is not None, f"{game['igdb_rating']} de 10 ({game['igdb_ratings_count']} votos)"),
        ("nota da crítica", game["critic_score"] is not None, f"{game['critic_score']} de 100"),
        ("classificação indicativa", bool(game["age_rating"]), str(game["age_rating"])),
        ("site oficial", bool(game["website"]), game["website"] or ""),
    ]
    for label, present, detail in checks:
        (report.ok if present else report.warn)(f"{label}: {detail}" if present else f"{label}: este jogo não tem")


def _age_ratings(report: Report) -> None:
    fields = ("name", "age_ratings.organization.name", "age_ratings.rating_category.rating")
    sample = igdb.fetch_json(
        Query("games", fields, igdb._MAIN_GAMES + (("total_rating_count", "notnull", None),), sort="total_rating_count desc", limit=_SAMPLE)
    )
    sample = [g for g in sample if isinstance(g, dict)] if isinstance(sample, list) else []
    with_items = [g for g in sample if g.get("age_ratings")]
    understood = [g for g in with_items if adult.age_ratings(g)]
    if not sample:
        report.fail("o IGDB não devolveu jogos para conferir as classificações")
        return
    report.ok(f"{len(with_items)} dos {len(sample)} jogos mais votados têm classificação etária; o DiscPlayer entendeu {len(understood)}")
    if len(understood) < len(with_items):
        shape = next(g["age_ratings"][0] for g in with_items if g not in understood)
        report.fail(f"há classificações num formato que o filtro não entende. Exemplo: {str(shape)[:200]}")
    pairs = sorted({pair for g in understood for pair in adult.age_ratings(g)})
    organizations = sorted({org for org, _ in pairs})
    report.info("organizações vistas: " + (", ".join(organizations) or "nenhuma"))
    for organization in organizations:
        report.info(f"  {organization}: " + ", ".join(sorted({r for o, r in pairs if o == organization})))
    unknown = sorted(o for o in organizations if o.lower() not in adult._RATINGS_MATURE_LEVEL)
    if unknown:
        report.warn("organizações que o filtro ainda não conhece (não escondem nada): " + ", ".join(unknown))
    brazil = sum(1 for g in understood if any(o.lower() == "classind" for o, _ in adult.age_ratings(g)))
    report.info(f"com a classificação do Brasil (ClassInd): {brazil} de {len(sample)}")


def _adult_filter(report: Report) -> None:
    level = adult.normalize_level(current_app.config.get("ADULT_CONTENT_FILTER"))
    report.info(f"nível do filtro em uso: {level}")
    theme = igdb.fetch_json(Query("themes", ("name", "slug"), (("id", "=", _ADULT_THEME_ID),), limit=1))
    slug = theme[0].get("slug") if isinstance(theme, list) and theme and isinstance(theme[0], dict) else None
    if slug == "erotic":
        report.ok("o tema número 42 do IGDB é mesmo “erotic” (o que o filtro procura)")
    else:
        report.fail(f"o tema número {_ADULT_THEME_ID} do IGDB agora é “{slug}”: o filtro precisa ser ajustado")
    fields = ("name", "age_ratings.organization.name", "age_ratings.rating_category.rating", "themes.slug")
    sample = igdb.fetch_json(Query("games", fields, (("themes", "in", (_ADULT_THEME_ID,)),), sort="total_rating_count desc", limit=_SAMPLE))
    sample = [g for g in sample if isinstance(g, dict)] if isinstance(sample, list) else []
    if not sample:
        report.warn("não achei jogos com o tema “erotic” para testar o filtro")
        return
    hidden = sum(1 for g in sample if adult.is_blocked(g, adult.EXPLICIT))
    (report.ok if hidden == len(sample) else report.fail)(f"{hidden} de {len(sample)} jogos com o tema “erotic” ficam escondidos no nível explicit")
    target = sample[0]
    asked = igdb.search_games(search=target["name"], page_size=20)["results"]
    if level == adult.OFF:
        report.info("o filtro está desligado (off): a busca por um jogo adulto o devolve normalmente.")
    elif any(g["igdb_id"] == target["id"] for g in asked):
        report.fail("a busca pelo nome de um jogo adulto ainda o devolve (o filtro não o escondeu)")
    else:
        report.ok("a busca pelo nome de um jogo adulto não o devolve")
    try:
        igdb.get_game(target["id"])
        if level == adult.OFF:
            report.info("a página de um jogo adulto abre (filtro desligado).")
        else:
            report.fail("a página de um jogo adulto abriu: ela devia estar indisponível")
    except igdb.IgdbBlocked:
        report.ok("a página de um jogo adulto fica indisponível")
    rated = [g for g in sample if any(o.lower() == "esrb" and r.upper() == "AO" for o, r in adult.age_ratings(g))]
    report.info(f"nesta amostra, {len(rated)} também têm a classificação ESRB Adults Only.")


def _images(report: Report) -> None:
    results = igdb.featured_games("popular", page_size=3)["results"]
    urls = [url for g in results[:1] for url in (g["cover_thumb_url"], g["cover_url"]) if url]
    if not urls:
        report.warn("nenhuma capa para testar")
        return
    for url in urls:
        try:
            response = requests.get(url, timeout=(3.05, 8.0), stream=True)
            kind = response.headers.get("Content-Type", "")
            response.close()
        except requests.ConnectionError as exc:
            # Hospedagens com lista de sites liberados (como o plano gratuito da PythonAnywhere) barram
            # `images.igdb.com` para o servidor. O DiscPlayer nunca baixa capas no servidor: ele só passa o
            # endereço, e quem baixa é o navegador de quem visita. Por isso, aqui, é aviso e não falha.
            report.warn(f"este servidor não alcança as capas ({type(exc).__name__}). Endereço: {url}")
            report.info(
                "Isso não afeta o site: quem baixa as capas é o navegador de quem visita, não o servidor. "
                "Só se preocupe se as capas também não aparecerem no site aberto no navegador."
            )
            return
        except requests.RequestException as exc:
            report.fail(f"não consegui baixar uma capa ({type(exc).__name__}). Endereço: {url}")
            continue
        if response.status_code == 200 and kind.startswith("image/"):
            report.ok(f"a capa abre ({kind}): {url.rsplit('/', 2)[-2]}/{url.rsplit('/', 1)[-1]}")
        else:
            report.fail(f"a capa respondeu HTTP {response.status_code} ({kind or 'sem tipo'}). Endereço: {url}")


# --------------------------------------------------------------------------------------------------- orquestração
def run(out: Callable[[str], None] = print, *, images: bool = True) -> int:
    """Roda todas as conferências dentro de um contexto de aplicação. Devolve o código de saída."""
    config = current_app.config
    report = Report(out, secrets=(config["IGDB_CLIENT_ID"], config["IGDB_CLIENT_SECRET"]))
    report._say("Conferência do IGDB — DiscPlayer")
    report.title("Credenciais")
    missing = [name for name in ("IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET") if not config[name]]
    if missing:
        report.fail("faltam no backend/.env: " + ", ".join(missing))
        report.info("Crie o aplicativo em https://dev.twitch.tv/console, copie o Client ID, gere um “New Secret” e")
        report.info("coloque os dois no backend/.env (IGDB_CLIENT_ID=… e IGDB_CLIENT_SECRET=…). Depois repita o comando.")
        return 2
    report.ok(f"IGDB_CLIENT_ID ({len(config['IGDB_CLIENT_ID'])} caracteres) e IGDB_CLIENT_SECRET ({len(config['IGDB_CLIENT_SECRET'])} caracteres) definidos")
    steps: list[tuple[str, Callable[[Report], None]]] = [
        ("Login na Twitch", _token),
        ("Gêneros", _genres),
        ("Plataformas", _platforms),
        ("Listas da página inicial", _lists),
        ("Busca", _search),
        ("Filtros e ordens do catálogo", _filters),
        ("Página de um jogo", _detail),
        ("Classificações etárias", _age_ratings),
        ("Filtro de conteúdo adulto", _adult_filter),
    ]
    if images:
        steps.append(("Imagens", _images))
    # O serviço registra em log cada recusa do IGDB; aqui elas já saem no relatório, então o log só atrapalharia.
    logger = logging.getLogger(igdb.__name__)
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        for title, check in steps:
            _step(report, title, lambda check=check: check(report))
            if title == "Login na Twitch" and report.fail_count:
                report.info("Sem o login não dá para continuar. Confira o Client ID e o Client Secret.")
                break
    finally:
        logger.setLevel(previous_level)
    report.title("Resumo")
    summary = f"{report.ok_count} ok, {report.warn_count} aviso(s), {report.fail_count} falha(s)"
    if report.fail_count:
        report._say(f"  ✖ {summary}. Copie a saída inteira (ela não mostra suas credenciais) e envie para eu ajustar.")
        return 1
    report._say(f"  ✔ {summary}." + (" Os avisos são informações, não erros." if report.warn_count else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.igdb_check", description="Confere a integração com o IGDB.")
    parser.add_argument("--sem-imagens", action="store_true", help="não tenta baixar capas")
    args = parser.parse_args(argv)
    from . import create_app

    app = create_app()
    with app.app_context():
        return run(images=not args.sem_imagens)


if __name__ == "__main__":
    sys.exit(main())
