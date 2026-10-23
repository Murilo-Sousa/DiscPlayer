"""RAWG simulada, só para testes e para desenvolver sem chave.

Não é a RAWG: são ~35 jogos conhecidos, com ids sintéticos (a partir de 900001, para
ninguém confundi-los com ids reais), descrições curtas escritas aqui e imagens que
não existem. O formato das respostas segue o da API real (campos `results`, `next`,
`parent_platforms`, `description_raw` etc.), de modo que o código de produção
percorre os mesmos caminhos.

Uso nos testes:   monkeypatch.setattr(rawg, "fetch_json", fake_rawg.fetch_json)
Uso por HTTP:     python -m tests.fake_rawg_server   (veja docs/desenvolvimento.md)
"""
from __future__ import annotations

from datetime import date, timedelta

from app.services.rawg import RawgNotFound

GENRES = {
    "action": (4, "Action"), "indie": (51, "Indie"), "adventure": (3, "Adventure"), "rpg": (5, "RPG"),
    "strategy": (10, "Strategy"), "shooter": (2, "Shooter"), "casual": (40, "Casual"),
    "simulation": (14, "Simulation"), "puzzle": (7, "Puzzle"), "arcade": (11, "Arcade"),
    "platformer": (83, "Platformer"), "racing": (1, "Racing"), "sports": (15, "Sports"),
    "fighting": (6, "Fighting"),
}
PARENT_PLATFORMS = {
    "pc": (1, "PC"), "playstation": (2, "PlayStation"), "xbox": (3, "Xbox"),
    "nintendo": (7, "Nintendo"), "linux": (6, "Linux"), "mac": (5, "macOS"),
}

# nome, lançamento, gêneros, plataformas, estúdio, metacritic, popularidade (added)
_RAW = [
    ("Hades", "2020-09-17", "action indie rpg", "pc playstation xbox nintendo mac", "Supergiant Games", 93, 9800),
    ("Celeste", "2018-01-25", "platformer indie", "pc playstation xbox nintendo linux mac", "Maddy Makes Games", 92, 9100),
    ("Hollow Knight", "2017-02-24", "platformer action indie", "pc playstation xbox nintendo linux mac", "Team Cherry", 87, 9500),
    ("Disco Elysium", "2019-10-15", "rpg adventure", "pc playstation xbox nintendo mac", "ZA/UM", 91, 6200),
    ("The Witcher 3: Wild Hunt", "2015-05-18", "rpg action", "pc playstation xbox nintendo", "CD PROJEKT RED", 92, 14500),
    ("Stardew Valley", "2016-02-26", "simulation rpg indie", "pc playstation xbox nintendo linux mac", "ConcernedApe", 89, 12000),
    ("Elden Ring", "2022-02-25", "rpg action", "pc playstation xbox", "FromSoftware", 96, 13000),
    ("Portal 2", "2011-04-18", "puzzle adventure action", "pc playstation xbox linux mac", "Valve", 95, 15200),
    ("Super Metroid", "1994-03-19", "platformer action adventure", "nintendo", "Nintendo R&D1", 0, 3900),
    ("Chrono Trigger", "1995-03-11", "rpg", "nintendo pc", "Square", 0, 4100),
    ("Half-Life 2", "2004-11-16", "shooter action", "pc xbox linux mac", "Valve", 96, 11800),
    ("Shadow of the Colossus", "2005-10-18", "action adventure", "playstation", "Team Ico", 91, 4800),
    ("Sekiro: Shadows Die Twice", "2019-03-22", "action adventure", "pc playstation xbox", "FromSoftware", 90, 7000),
    ("Outer Wilds", "2019-05-28", "adventure puzzle indie", "pc playstation xbox", "Mobius Digital", 85, 6900),
    ("Return of the Obra Dinn", "2018-10-18", "puzzle adventure indie", "pc playstation xbox nintendo mac", "Lucas Pope", 88, 4300),
    ("Baldur's Gate 3", "2023-08-03", "rpg strategy adventure", "pc playstation xbox mac", "Larian Studios", 96, 10500),
    ("The Legend of Zelda: Breath of the Wild", "2017-03-03", "action adventure", "nintendo", "Nintendo EPD", 97, 9900),
    ("Persona 5 Royal", "2020-03-31", "rpg", "pc playstation xbox nintendo", "Atlus", 95, 5400),
    ("Undertale", "2015-09-15", "rpg indie adventure", "pc playstation xbox nintendo linux mac", "tobyfox", 92, 8200),
    ("Hotline Miami", "2012-10-23", "action shooter indie", "pc playstation linux mac", "Dennaton Games", 85, 5100),
    ("Dark Souls", "2011-09-22", "rpg action", "pc playstation xbox", "FromSoftware", 89, 7600),
    ("Resident Evil 4", "2005-01-11", "shooter action adventure", "pc playstation xbox nintendo", "Capcom", 96, 6400),
    ("God of War", "2018-04-20", "action adventure rpg", "pc playstation", "Santa Monica Studio", 94, 9300),
    ("Red Dead Redemption 2", "2018-10-26", "action adventure", "pc playstation xbox", "Rockstar Games", 97, 14800),
    ("Cyberpunk 2077", "2020-12-10", "rpg action shooter", "pc playstation xbox", "CD PROJEKT RED", 86, 12400),
    ("Minecraft", "2011-11-18", "simulation adventure", "pc playstation xbox nintendo linux mac", "Mojang Studios", 93, 16000),
    ("Tetris Effect", "2018-11-09", "puzzle arcade", "pc playstation xbox nintendo", "Monstars", 89, 2100),
    ("Forza Horizon 5", "2021-11-09", "racing sports", "pc xbox", "Playground Games", 92, 5200),
    ("Street Fighter II", "1991-02-06", "fighting arcade", "nintendo pc", "Capcom", 0, 3100),
    ("Civilization VI", "2016-10-21", "strategy simulation", "pc playstation xbox nintendo linux mac", "Firaxis Games", 88, 5900),
    ("Slay the Spire", "2019-01-23", "strategy indie rpg", "pc playstation xbox nintendo mac", "Mega Crit", 89, 4600),
    ("Hades II", "2024-05-06", "action indie rpg", "pc", "Supergiant Games", 0, 3800),
    ("Pizza Tower", "2023-01-26", "platformer action indie", "pc", "Tour De Pizza", 0, 1400),
    ("Balatro", "2024-02-20", "strategy indie arcade", "pc playstation xbox nintendo mac", "LocalThunk", 90, 3300),
]

_FICTIONAL_NEW = [  # lançamentos recentes inventados (datas relativas a hoje), só para a faixa "novos"
    ("Lantern Drift", 6, "adventure indie", "pc playstation", "Estúdio Brasa"),
    ("Quiet Orbit", 12, "puzzle indie", "pc nintendo", "Pequeno Satélite"),
    ("Ferrugem", 19, "action indie platformer", "pc xbox", "Casa Cinza"),
    ("Mapa das Marés", 27, "simulation casual", "pc nintendo mac", "Maré Alta Games"),
    ("Último Trem para Vila Nova", 33, "adventure rpg", "pc playstation", "Linha Oeste"),
    ("Cartucho Quebrado", 41, "arcade action", "pc nintendo", "Oficina Quatro Bits"),
    ("Nó de Sal", 55, "strategy indie", "pc linux", "Sal & Pimenta"),
    ("Coro de Vidro", 68, "rpg indie", "pc playstation xbox", "Voz Aberta"),
]


def _slug(name: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def _build() -> list[dict]:
    games = []
    for index, (name, released, genres, platforms, studio, metacritic, added) in enumerate(_RAW):
        games.append(_game(900001 + index, name, released, genres, platforms, studio, metacritic or None, added))
    today = date.today()
    for index, (name, days_ago, genres, platforms, studio) in enumerate(_FICTIONAL_NEW):
        released = (today - timedelta(days=days_ago)).isoformat()
        games.append(_game(900101 + index, name, released, genres, platforms, studio, None, 900 - index * 60))
    return games


def _game(rawg_id, name, released, genres, platforms, studio, metacritic, added) -> dict:
    slug = _slug(name)
    return {
        "id": rawg_id,
        "slug": slug,
        "name": name,
        "released": released,
        "background_image": f"https://media.rawg.io/media/games/fake/{slug}.jpg",
        "background_image_additional": f"https://media.rawg.io/media/games/fake/{slug}-2.jpg",
        "metacritic": metacritic,
        "added": added,
        "rating": round(3.2 + (added % 17) / 10, 2),
        "ratings_count": added // 4,
        "playtime": (added % 40) + 3,
        "genres": [{"id": GENRES[g][0], "name": GENRES[g][1], "slug": g} for g in genres.split()],
        "parent_platforms": [
            {"platform": {"id": PARENT_PLATFORMS[p][0], "name": PARENT_PLATFORMS[p][1], "slug": p}}
            for p in platforms.split()
        ],
        "developers": [{"id": 1, "name": studio, "slug": _slug(studio)}],
        "publishers": [{"id": 2, "name": studio, "slug": _slug(studio)}],
        "description_raw": (
            f"Descrição de teste de {name}. Este texto foi escrito para o ambiente de testes "
            "e não vem da RAWG.\n\nSegundo parágrafo, para verificar a quebra de linhas."
        ),
        "description": f"<p>Descrição de teste de {name}.</p><p>Segundo <b>parágrafo</b>.</p>",
        "website": "",
        "esrb_rating": {"id": 4, "name": "Mature", "slug": "mature"},
    }


GAMES: list[dict] = _build()
BY_ID = {g["id"]: g for g in GAMES}


def by_name(name: str) -> dict:
    return next(g for g in GAMES if g["name"] == name)


def _summary(game: dict) -> dict:
    keys = (
        "id", "slug", "name", "released", "background_image", "metacritic", "rating",
        "ratings_count", "playtime", "genres", "parent_platforms", "added",
    )
    return {k: game[k] for k in keys}


def _in_range(released: str | None, dates: str | None) -> bool:
    if not dates:
        return True
    start, end = dates.split(",")
    return bool(released) and start <= released <= end


def _listing(params: dict) -> dict:
    items = list(GAMES)
    if params.get("search"):
        term = str(params["search"]).lower()
        items = [g for g in items if term in g["name"].lower()]
    if params.get("genres"):
        wanted = set(str(params["genres"]).split(","))
        items = [g for g in items if wanted & {x["slug"] for x in g["genres"]} or wanted & {str(x["id"]) for x in g["genres"]}]
    if params.get("parent_platforms"):
        wanted = set(str(params["parent_platforms"]).split(","))
        items = [g for g in items if wanted & {str(p["platform"]["id"]) for p in g["parent_platforms"]}]
    items = [g for g in items if _in_range(g["released"], params.get("dates"))]

    ordering = str(params.get("ordering") or "")
    if ordering:
        field = ordering.lstrip("-")
        present = [g for g in items if g.get(field) not in (None, "")]
        missing = [g for g in items if g.get(field) in (None, "")]  # sem valor: sempre no fim
        present.sort(
            key=lambda g: g[field].lower() if isinstance(g[field], str) else g[field],
            reverse=ordering.startswith("-"),
        )
        items = present + missing
    page = int(params.get("page") or 1)
    size = int(params.get("page_size") or 20)
    start = (page - 1) * size
    chunk = items[start:start + size]
    return {
        "count": len(items),
        "next": "https://api.rawg.io/api/games?page=%d" % (page + 1) if start + size < len(items) else None,
        "previous": "https://api.rawg.io/api/games?page=%d" % (page - 1) if page > 1 else None,
        "results": [_summary(g) for g in chunk],
    }


def fetch_json(path: str, params: dict | None = None):
    """Mesma assinatura de app.services.rawg.fetch_json."""
    params = dict(params or {})
    path = path.strip("/")
    if path == "games":
        return _listing(params)
    if path == "genres":
        return {"count": len(GENRES), "results": [{"id": i, "name": n, "slug": s} for s, (i, n) in sorted(GENRES.items(), key=lambda kv: kv[1][1])]}
    if path == "platforms/lists/parents":
        return {"count": len(PARENT_PLATFORMS), "results": [{"id": i, "name": n, "slug": s, "platforms": []} for s, (i, n) in PARENT_PLATFORMS.items()]}
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "games" and parts[1].isdigit():
        game = BY_ID.get(int(parts[1]))
        if game is None:
            raise RawgNotFound()
        if len(parts) == 2:
            return {**_summary(game), **{k: game[k] for k in (
                "description_raw", "description", "developers", "publishers", "website",
                "esrb_rating", "background_image_additional")},
                "name_original": game["name"], "platforms": game["parent_platforms"]}
        if parts[2] == "screenshots":
            return {"count": 3, "results": [
                {"id": i, "image": f"https://media.rawg.io/media/screenshots/fake/{game['slug']}-{i}.jpg"} for i in (1, 2, 3)
            ]}
    raise RawgNotFound()
