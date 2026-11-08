"""IGDB simulado, só para testes e para desenvolver sem credenciais.

Não é o IGDB: são ~35 jogos conhecidos, com ids sintéticos (a partir de 900001, para ninguém confundi-los com ids
reais), descrições curtas escritas aqui e imagens que não existem. O formato das respostas segue o da API real
(`cover.image_id`, `first_release_date` em segundos, `genres`, `age_ratings`, `themes`...), de modo que o código de
produção percorre os mesmos caminhos. Como o IGDB, ele devolve só os campos pedidos (o primeiro nível deles) e
omite os que estão vazios.

Uso nos testes:   monkeypatch.setattr(igdb, "fetch_json", fake_igdb.fetch_json)
Uso por HTTP:     python -m tests.fake_igdb_server   (veja docs/desenvolvimento.md)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.igdb import Query

# Os gêneros do IGDB (ids e slugs reais).
GENRES = {
    "point-and-click": (2, "Point-and-click"), "fighting": (4, "Fighting"), "shooter": (5, "Shooter"),
    "music": (7, "Music"), "platform": (8, "Platform"), "puzzle": (9, "Puzzle"), "racing": (10, "Racing"),
    "real-time-strategy-rts": (11, "Real Time Strategy (RTS)"), "role-playing-rpg": (12, "Role-playing (RPG)"),
    "simulator": (13, "Simulator"), "sport": (14, "Sport"), "strategy": (15, "Strategy"),
    "turn-based-strategy-tbs": (16, "Turn-based strategy (TBS)"), "tactical": (24, "Tactical"),
    "hack-and-slash-beat-em-up": (25, "Hack and slash/Beat 'em up"), "quiz-trivia": (26, "Quiz/Trivia"),
    "pinball": (30, "Pinball"), "adventure": (31, "Adventure"), "indie": (32, "Indie"), "arcade": (33, "Arcade"),
    "visual-novel": (34, "Visual Novel"), "card-and-board-game": (35, "Card & Board Game"), "moba": (36, "MOBA"),
}
# Os nomes curtos que os dados abaixo usam, para o gênero do IGDB.
_GENRE_OF = {
    "action": "hack-and-slash-beat-em-up", "indie": "indie", "adventure": "adventure", "rpg": "role-playing-rpg",
    "strategy": "strategy", "shooter": "shooter", "casual": "card-and-board-game", "simulation": "simulator",
    "puzzle": "puzzle", "arcade": "arcade", "platformer": "platform", "racing": "racing", "sports": "sport",
    "fighting": "fighting",
}
# Plataformas do IGDB (ids reais) usadas pelos jogos de teste.
PLATFORMS = {
    3: ("Linux", "Linux"), 6: ("PC (Microsoft Windows)", "PC"), 14: ("Mac", "Mac"), 48: ("PlayStation 4", "PS4"),
    167: ("PlayStation 5", "PS5"), 49: ("Xbox One", "XONE"), 169: ("Xbox Series X|S", "Series X|S"),
    130: ("Nintendo Switch", "Switch"),
}
_PLATFORMS_OF = {
    "pc": (6,), "playstation": (48, 167), "xbox": (49, 169), "nintendo": (130,), "linux": (3,), "mac": (14,),
}

THEMES = {
    "action": (1, "Action"), "fantasy": (17, "Fantasy"), "horror": (19, "Horror"), "erotic": (42, "Erotic"),
}
ORGANIZATIONS = {"ESRB": 1, "PEGI": 2, "ClassInd": 6}
# Como o IGDB de verdade escreve o nome de cada organização (conferido com `python -m app.igdb_check`).
_ORGANIZATION_NAMES = {"ClassInd": "CLASS_IND"}

# Classificações da ESRB por jogo; quem não está aqui é "T" (Teen). Valores só para o ambiente de testes.
_ESRB_BY_NAME = {
    "Celeste": "E10+", "Stardew Valley": "E10+", "Minecraft": "E10+", "Tetris Effect": "E", "Super Metroid": "E",
    "The Witcher 3: Wild Hunt": "M", "Disco Elysium": "M", "Elden Ring": "M", "Cyberpunk 2077": "M",
    "Red Dead Redemption 2": "M", "Baldur's Gate 3": "M", "Resident Evil 4": "M", "Hotline Miami": "M",
    "Half-Life 2": "M", "God of War": "M",
}
# Alguns jogos também têm a classificação do Brasil (ClassInd) e a da Europa (PEGI).
_CLASSIND_BY_NAME = {"Hades": "14", "Celeste": "10", "The Witcher 3: Wild Hunt": "18", "Tetris Effect": "L"}
_PEGI_BY_NAME = {"The Witcher 3: Wild Hunt": "18", "Hades": "12"}

# nome, lançamento, gêneros, plataformas, estúdio, crítica (aggregated_rating), popularidade (nº de notas × 4)
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

_FICTIONAL_UPCOMING = [  # ainda não lançados (datas relativas a hoje): só para testar o que um jogo sem lançamento permite
    ("Farol do Amanhã", 400, "adventure indie", "pc nintendo", "Estúdio Horizonte"),
]

# conteúdo adulto inventado (datas relativas a hoje), só para testar o filtro (pouco populares: ficam no fim das
# listas). nome, dias atrás, gêneros, plataformas, estúdio, classificações [(organização, nota)], temas
_FICTIONAL_ADULT = [
    ("Jardim Proibido", 120, "adventure indie", "pc", "Estúdio Sombra", (("ESRB", "AO"),), ()),
    ("Noite Sem Censura", 200, "simulation casual", "pc", "Lua Vermelha", (), ("erotic",)),
    ("Quarto Dezoito", 150, "puzzle casual", "pc", "Casa Escura", (), ("erotic", "fantasy")),
]


def _slug(name: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def _stamp(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _build() -> list[dict]:
    games = []
    for index, (name, released, genres, platforms, studio, critic, added) in enumerate(_RAW):
        games.append(_game(900001 + index, name, released, genres, platforms, studio, critic or None, added))
    today = date.today()
    for index, (name, days_ago, genres, platforms, studio) in enumerate(_FICTIONAL_NEW):
        released = (today - timedelta(days=days_ago)).isoformat()
        games.append(_game(900101 + index, name, released, genres, platforms, studio, None, 900 - index * 60))
    for index, (name, days_ahead, genres, platforms, studio) in enumerate(_FICTIONAL_UPCOMING):
        released = (today + timedelta(days=days_ahead)).isoformat()
        games.append(_game(900201 + index, name, released, genres, platforms, studio, None, 10))
    for index, (name, days_ago, genres, platforms, studio, ratings, themes) in enumerate(_FICTIONAL_ADULT):
        released = (today - timedelta(days=days_ago)).isoformat()
        games.append(_game(900301 + index, name, released, genres, platforms, studio, None, 50 - index,
                           ratings=ratings, themes=themes))
    # Uma expansão (tem jogo-pai): o catálogo só mostra jogos principais, então ela nunca aparece nas listas.
    games.append({**_game(900401, "Hades: Pacote de Teste", "2021-01-01", "action", "pc", "Supergiant Games", None, 8000),
                  "parent_game": 900001})
    return games


def _game(igdb_id, name, released, genres, platforms, studio, critic, added, *, ratings=None, themes=None) -> dict:
    slug = _slug(name)
    if ratings is None:
        ratings = [("ESRB", _ESRB_BY_NAME.get(name, "T"))]
        if name in _CLASSIND_BY_NAME:
            ratings.append(("ClassInd", _CLASSIND_BY_NAME[name]))
        if name in _PEGI_BY_NAME:
            ratings.append(("PEGI", _PEGI_BY_NAME[name]))
    if themes is None:
        themes = ("fantasy",) if name == "The Witcher 3: Wild Hunt" else ("action",)
    platform_ids = [pid for key in platforms.split() for pid in _PLATFORMS_OF[key]]
    game = {
        "id": igdb_id,
        "name": name,
        "slug": slug,
        "cover": {"id": igdb_id, "image_id": f"co{igdb_id}"},
        "first_release_date": _stamp(released),
        "genres": [{"id": GENRES[g][0], "name": GENRES[g][1], "slug": g} for g in dict.fromkeys(_GENRE_OF[t] for t in genres.split())],
        "platforms": [{"id": pid, "name": PLATFORMS[pid][0], "abbreviation": PLATFORMS[pid][1]} for pid in platform_ids],
        "total_rating": round((3.2 + (added % 17) / 10) * 20, 2),
        "total_rating_count": added // 4,
        "summary": (
            f"Descrição de teste de {name}. Este texto foi escrito para o ambiente de testes "
            "e não vem do IGDB.\n\nSegundo parágrafo, para verificar a quebra de linhas."
        ),
        "screenshots": [{"id": igdb_id * 10 + n, "image_id": f"sc{igdb_id}{n}"} for n in (1, 2, 3)],
        "artworks": [{"id": igdb_id, "image_id": f"ar{igdb_id}"}],
        "websites": [
            {"url": f"https://store.steampowered.com/app/{igdb_id}"},  # loja: não vale como site oficial
            {"url": f"https://{slug}.jogo.exemplo.com"},
        ],
        "involved_companies": [
            {"developer": True, "publisher": False, "company": {"id": 1, "name": studio}},
            {"developer": False, "publisher": True, "company": {"id": 2, "name": studio}},
        ],
        "age_ratings": [
            {"organization": {"id": ORGANIZATIONS[org], "name": _ORGANIZATION_NAMES.get(org, org)}, "rating_category": {"id": 1, "rating": rating}}
            for org, rating in ratings
        ],
        "themes": [{"id": THEMES[t][0], "name": THEMES[t][1], "slug": t} for t in themes],
    }
    if critic:
        game["aggregated_rating"] = float(critic)
        game["aggregated_rating_count"] = 12
    return game


GAMES: list[dict] = _build()
BY_ID = {g["id"]: g for g in GAMES}
MAIN_GAMES = [g for g in GAMES if "parent_game" not in g]  # os que o catálogo lista (sem expansões)


def by_name(name: str) -> dict:
    return next(g for g in GAMES if g["name"] == name)


# ------------------------------------------------------------------- a consulta
def _value(game: dict, field: str):
    return game.get(field)


def _matches(game: dict, clause: tuple) -> bool:
    field, op, wanted = clause
    value = _value(game, field)
    if op == "null":
        return value in (None, [], "")
    if op == "notnull":
        return value not in (None, [], "")
    if op == "in":
        values = value if isinstance(value, list) else [value]
        ids = {v["id"] if isinstance(v, dict) else v for v in values}
        return bool(ids & set(wanted))
    if value is None:
        return False
    return {
        "=": value == wanted, ">=": value >= wanted, "<=": value <= wanted, ">": value > wanted, "<": value < wanted,
    }[op]


def _project(game: dict, fields: tuple[str, ...]) -> dict:
    """Como o IGDB: só os campos pedidos (o primeiro nível deles) e o id; o que está vazio não vem."""
    keys = {"id"} | {f.split(".")[0] for f in fields}
    return {k: v for k, v in game.items() if k in keys and v not in (None, [], "")}


def _games(query: Query):
    items = [g for g in GAMES if all(_matches(g, c) for c in query.filters)]
    if query.search:
        term = query.search.lower()
        items = [g for g in items if term in g["name"].lower()]
    if query.sort:
        field, direction = query.sort.split(" ")
        present = [g for g in items if g.get(field) not in (None, "")]
        missing = [g for g in items if g.get(field) in (None, "")]  # sem valor: sempre no fim
        present.sort(key=lambda g: g[field].lower() if isinstance(g[field], str) else g[field], reverse=direction == "desc")
        items = present + missing
    return items


def fetch_json(query: Query):
    """Mesma assinatura de app.services.igdb.fetch_json."""
    endpoint = query.endpoint.strip("/")
    if endpoint == "games":
        items = _games(query)
        if query.count:
            return {"count": len(items)}
        chunk = items[query.offset:query.offset + query.limit]
        return [_project(g, query.fields) for g in chunk]
    if endpoint == "genres":
        rows = [{"id": i, "name": n, "slug": s} for s, (i, n) in sorted(GENRES.items(), key=lambda kv: kv[1][1])]
        return rows[:query.limit]
    if endpoint == "platforms":
        wanted = {c[2] for c in query.filters if c[0] == "id"} | {v for c in query.filters if c[1] == "in" for v in c[2]}
        return [{"id": pid, "name": PLATFORMS[pid][0]} for pid in PLATFORMS if not wanted or pid in wanted]
    if endpoint == "themes":
        wanted = {c[2] for c in query.filters if c[0] == "id"} | {v for c in query.filters if c[1] == "in" for v in c[2]}
        return [{"id": i, "name": n, "slug": s} for s, (i, n) in THEMES.items() if not wanted or i in wanted]
    return []
