"""Integração com o IGDB (https://api-docs.igdb.com/), o banco de jogos da Twitch.

Só o back-end conversa com o IGDB: o Client ID e o Client Secret ficam no servidor (IGDB_CLIENT_ID e
IGDB_CLIENT_SECRET) e nunca chegam ao navegador. As respostas são normalizadas para um formato próprio do
DiscPlayer (o front-end não depende do formato do IGDB) e nenhum campo é tratado como garantido: quando o IGDB
omite algo, o campo vem vazio.

Como funciona:

- A autenticação é OAuth2 da Twitch (`client_credentials`): o token dura semanas, fica em memória e é renovado
  sozinho quando expira ou quando o IGDB o recusa.
- As consultas usam a linguagem Apicalypse (um texto como `fields name; where id = 5; limit 1;`). O código monta
  um `Query` com valores já validados (números, nomes de campos fixos) e só `to_apicalypse` o transforma em texto,
  então nada digitado por alguém vira parte da consulta sem ser tratado.
- O limite do IGDB é de 4 requisições por segundo: há um espaçamento entre as chamadas e um cache com validade,
  que também serve a cópia expirada se o serviço cair.

Termos: o uso gratuito vale para projetos não comerciais, nos termos do Twitch Developer Service Agreement.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from flask import current_app

from ..utils.cache import TTLCache
from ..utils.dates import today_utc
from ..utils.text import strip_html
from . import adult

logger = logging.getLogger(__name__)

_session = requests.Session()
_cache = TTLCache(max_entries=1500)

# Ordenações oferecidas ao usuário (a chave vai na URL do catálogo).
ORDERINGS: dict[str, str | None] = {
    "relevance": None,  # relevância da própria busca
    "popular": "total_rating_count desc",
    "released": "first_release_date desc",
    "rating": "total_rating desc",
    "critics": "aggregated_rating desc",
    "name": "name asc",
}

# Agrupamento das plataformas do IGDB (dezenas, uma por console e versão) nas famílias que o catálogo mostra.
# `id` é o número usado na URL do catálogo; `igdb_ids` são as plataformas do IGDB que cada grupo reúne.
PLATFORM_GROUPS = (
    {"id": 1, "slug": "pc", "name": "PC", "igdb_ids": (6,)},
    {"id": 2, "slug": "playstation", "name": "PlayStation", "igdb_ids": (7, 8, 9, 38, 46, 48, 167)},
    {"id": 3, "slug": "xbox", "name": "Xbox", "igdb_ids": (11, 12, 49, 169)},
    {"id": 7, "slug": "nintendo", "name": "Nintendo", "igdb_ids": (4, 5, 18, 19, 20, 21, 22, 24, 33, 37, 41, 130, 508)},
    {"id": 5, "slug": "mac", "name": "macOS", "igdb_ids": (14,)},
    {"id": 6, "slug": "linux", "name": "Linux", "igdb_ids": (3,)},
    {"id": 4, "slug": "ios", "name": "iOS", "igdb_ids": (39,)},
    {"id": 8, "slug": "android", "name": "Android", "igdb_ids": (34,)},
)
_GROUP_BY_PLATFORM = {pid: group for group in PLATFORM_GROUPS for pid in group["igdb_ids"]}
_GROUP_BY_ID = {group["id"]: group for group in PLATFORM_GROUPS}

# Os nomes dos gêneros chegam em inglês; estes (por slug do IGDB) aparecem em português. Slug desconhecido usa o
# nome que o IGDB mandou.
GENRE_NAMES = {
    "point-and-click": "Point-and-click", "fighting": "Luta", "shooter": "Tiro", "music": "Música",
    "platform": "Plataforma", "puzzle": "Quebra-cabeça", "racing": "Corrida",
    "real-time-strategy-rts": "Estratégia em tempo real", "role-playing-rpg": "RPG", "simulator": "Simulação",
    "sport": "Esporte", "strategy": "Estratégia", "turn-based-strategy-tbs": "Estratégia por turnos",
    "tactical": "Tático", "hack-and-slash-beat-em-up": "Hack and slash", "quiz-trivia": "Quiz",
    "pinball": "Pinball", "adventure": "Aventura", "indie": "Indie", "arcade": "Arcade",
    "visual-novel": "Visual novel", "card-and-board-game": "Cartas e tabuleiro", "moba": "MOBA",
}

# Endereços de lojas e redes sociais: não valem como "site oficial".
_NOT_OFFICIAL = (
    "steampowered.com", "steamcommunity.com", "gog.com", "epicgames.com", "itch.io", "store.", "apps.apple.com",
    "play.google.com", "microsoft.com", "xbox.com", "playstation.com", "nintendo.com", "facebook.com", "twitter.com",
    "x.com", "instagram.com", "youtube.com", "youtu.be", "twitch.tv", "reddit.com", "discord.gg", "discord.com",
    "wikipedia.org", "fandom.com", "wikia.com", "tiktok.com", "bsky.app", "mastodon", "kickstarter.com",
)

_IMAGE_HOST = "https://images.igdb.com/igdb/image/upload"
_IMAGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


# ------------------------------------------------------------------------- erros
class IgdbError(Exception):
    status = 502
    code = "igdb_error"
    message = "Não foi possível consultar o IGDB."

    def __init__(self, message: str | None = None, retry_after: int | None = None, detail: str | None = None):
        self.message = message or self.message
        self.retry_after = retry_after
        # O que o IGDB disse (quando disse algo). Serve ao `igdb_check` e aos logs; nunca vai para a resposta da API.
        self.detail = detail
        super().__init__(self.message)


class IgdbNotConfigured(IgdbError):
    status = 503
    code = "igdb_not_configured"
    message = (
        "A integração com o IGDB não está configurada. "
        "Defina IGDB_CLIENT_ID e IGDB_CLIENT_SECRET no arquivo backend/.env e reinicie o servidor."
    )


class IgdbNotFound(IgdbError):
    status = 404
    code = "game_not_found"
    message = "Jogo não encontrado no IGDB."


class IgdbBlocked(IgdbNotFound):
    """O jogo existe no IGDB, mas é conteúdo adulto e o filtro (ADULT_CONTENT_FILTER) o esconde.

    É um "não encontrado" (404) de propósito: as rotas que já repassam o 404 do IGDB fazem o mesmo aqui, sem
    servir nem a cópia local do jogo.
    """

    code = "game_blocked"
    message = "Este jogo não está disponível aqui: o DiscPlayer não mostra jogos com conteúdo adulto."


class IgdbRateLimited(IgdbError):
    status = 429
    code = "igdb_rate_limited"
    message = "O limite de consultas ao IGDB foi atingido. Tente novamente em alguns minutos."


class IgdbUnavailable(IgdbError):
    status = 503
    code = "igdb_unavailable"
    message = "O IGDB está indisponível no momento. Tente novamente em instantes."


# ----------------------------------------------------------------------- consulta
@dataclass(frozen=True)
class Query:
    """Uma consulta ao IGDB, ainda sem texto. Os filtros são tuplas (campo, operador, valor):

    ("id", "=", 5)                 id = 5
    ("genres", "in", (4, 5))       genres = (4,5)       (qualquer um dos valores)
    ("first_release_date", ">=", ts)  também "<=", ">" e "<"
    ("parent_game", "null", None)  parent_game = null
    ("cover", "notnull", None)     cover != null
    """

    endpoint: str
    fields: tuple[str, ...] = ()
    filters: tuple[tuple, ...] = ()
    search: str | None = None
    sort: str | None = None
    limit: int = 10
    offset: int = 0
    count: bool = False  # só quantos resultados há (endpoint /count)


_FIELD = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$")
_SORT = re.compile(r"^[a-z_][a-z0-9_.]* (asc|desc)$")
_COMPARISONS = {"=", ">=", "<=", ">", "<"}


def _number(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"valor numérico esperado, recebi {value!r}")
    return value


def _clause(field: str, op: str, value) -> str:
    if not _FIELD.match(field):
        raise ValueError(f"campo inválido: {field!r}")
    if op == "null":
        return f"{field} = null"
    if op == "notnull":
        return f"{field} != null"
    if op == "in":
        numbers = [str(_number(v)) for v in value]
        if not numbers:
            raise ValueError("lista vazia")
        return f"{field} = ({','.join(numbers)})"
    if op in _COMPARISONS:
        return f"{field} {op} {_number(value)}"
    raise ValueError(f"operador inválido: {op!r}")


def clean_search(term: str) -> str:
    """O texto da busca sem aspas, barras e caracteres de controle: ele entra entre aspas na consulta."""
    return " ".join(re.sub(r'[\x00-\x1f"\\;]', " ", term or "").split())[:100]


def to_apicalypse(query: Query) -> str:
    """O texto Apicalypse da consulta (o que o IGDB espera no corpo da requisição)."""
    parts: list[str] = []
    if not query.count:
        if not query.fields or not all(_FIELD.match(f) or f == "*" for f in query.fields):
            raise ValueError("campos inválidos")
        parts.append("fields " + ",".join(query.fields) + ";")
    if query.filters:
        parts.append("where " + " & ".join(_clause(*f) for f in query.filters) + ";")
    if query.search:
        parts.append(f'search "{clean_search(query.search)}";')
    if not query.count:
        if query.sort:
            if not _SORT.match(query.sort):
                raise ValueError(f"ordem inválida: {query.sort!r}")
            parts.append(f"sort {query.sort};")
        parts.append(f"limit {_number(query.limit)};")
        parts.append(f"offset {_number(query.offset)};")
    return " ".join(parts)


# --------------------------------------------------------------------- transporte
_token_lock = threading.Lock()
_token: dict = {"value": None, "expires_at": 0.0}
_throttle_lock = threading.Lock()
_next_slot = 0.0


def _wait_turn(interval: float) -> None:
    """Reserva a próxima vaga de requisição (o IGDB aceita 4 por segundo) e espera até ela, fora do lock."""
    global _next_slot
    if interval <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        start = max(now, _next_slot)
        _next_slot = start + interval
    if start > now:
        time.sleep(start - now)


def _credentials() -> tuple[str, str]:
    config = current_app.config
    client_id, secret = config["IGDB_CLIENT_ID"], config["IGDB_CLIENT_SECRET"]
    if not client_id or not secret:
        raise IgdbNotConfigured()
    return client_id, secret


def _access_token(*, force: bool = False) -> str:
    """O token da Twitch, pedido só quando falta ou vai vencer (a Twitch os entrega por semanas)."""
    client_id, secret = _credentials()
    with _token_lock:
        if not force and _token["value"] and time.monotonic() < _token["expires_at"]:
            return _token["value"]
        config = current_app.config
        try:
            response = _session.post(
                config["IGDB_TOKEN_URL"],
                data={"client_id": client_id, "client_secret": secret, "grant_type": "client_credentials"},
                timeout=config["IGDB_TIMEOUT"],
            )
        except requests.Timeout:
            logger.warning("IGDB: timeout ao pedir o token da Twitch")
            raise IgdbUnavailable("A Twitch demorou demais para responder. Tente novamente.") from None
        except requests.RequestException as exc:
            # Não registramos a mensagem da exceção: ela pode conter a URL com as credenciais.
            logger.warning("IGDB: falha de conexão ao pedir o token (%s)", type(exc).__name__)
            raise IgdbUnavailable() from None
        if response.status_code in (400, 401, 403):
            logger.error("A Twitch recusou as credenciais do IGDB (HTTP %s)", response.status_code)
            raise IgdbNotConfigured("A Twitch recusou as credenciais. Confira IGDB_CLIENT_ID e IGDB_CLIENT_SECRET.")
        if response.status_code != 200:
            logger.warning("IGDB: HTTP %s ao pedir o token", response.status_code)
            raise IgdbUnavailable()
        try:
            body = response.json()
            value, lifetime = body["access_token"], float(body.get("expires_in") or 3600)
        except (ValueError, KeyError, TypeError):
            logger.warning("IGDB: resposta inesperada ao pedir o token")
            raise IgdbUnavailable("A Twitch enviou uma resposta inesperada.") from None
        _token["value"] = value
        _token["expires_at"] = time.monotonic() + max(60.0, lifetime - 300)  # renova 5 minutos antes de vencer
        return value


def clear_token() -> None:
    with _token_lock:
        _token["value"], _token["expires_at"] = None, 0.0


def fetch_json(query: Query):
    """POST no IGDB. É o único ponto de rede do módulo (os testes o substituem)."""
    config = current_app.config
    client_id, _ = _credentials()
    endpoint = query.endpoint.strip("/") + ("/count" if query.count else "")
    url = f"{config['IGDB_BASE_URL']}/{endpoint}"
    body = to_apicalypse(query)
    for attempt in (1, 2):
        _wait_turn(config["IGDB_MIN_INTERVAL"])
        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {_access_token(force=attempt == 2)}",
            "Accept": "application/json",
            "User-Agent": "DiscPlayer/1.0",
        }
        try:
            response = _session.post(url, data=body.encode("utf-8"), headers=headers, timeout=config["IGDB_TIMEOUT"])
        except requests.Timeout:
            logger.warning("IGDB: timeout em /%s", endpoint)
            raise IgdbUnavailable("O IGDB demorou demais para responder. Tente novamente.") from None
        except requests.RequestException as exc:
            logger.warning("IGDB: falha de conexão em /%s (%s)", endpoint, type(exc).__name__)
            raise IgdbUnavailable() from None
        status = response.status_code
        if status == 401 and attempt == 1:
            continue  # o token pode ter sido revogado: pede outro e tenta uma vez mais
        if status in (401, 403):
            logger.error("O IGDB recusou as credenciais (HTTP %s)", status)
            raise IgdbNotConfigured("O IGDB recusou as credenciais. Confira IGDB_CLIENT_ID e IGDB_CLIENT_SECRET.")
        if status == 429:
            retry = response.headers.get("Retry-After", "")
            raise IgdbRateLimited(retry_after=int(retry) if retry.isdigit() else None)
        if status == 400:
            # Consulta que o IGDB não entendeu: é erro nosso, não de quem usa. O texto dele ajuda a achar o campo.
            logger.error("IGDB: consulta recusada em /%s: %s | %s", endpoint, getattr(response, "text", "")[:300], body)
            raise IgdbUnavailable("O IGDB não entendeu a consulta.", detail=str(getattr(response, "text", ""))[:300])
        if status != 200:
            logger.warning("IGDB: HTTP %s em /%s", status, endpoint)
            raise IgdbUnavailable()
        try:
            return response.json()
        except ValueError:
            logger.warning("IGDB: resposta que não é JSON em /%s", endpoint)
            raise IgdbUnavailable("O IGDB enviou uma resposta inesperada.") from None
    raise IgdbUnavailable()  # (inalcançável: o laço sempre retorna ou levanta)


def _cached(key: tuple, ttl_name: str, loader):
    """Cache com tolerância a falhas: se o IGDB cair, usa o último valor guardado."""
    hit = _cache.get(key)
    if hit is not None:
        return hit
    try:
        value = loader()
    except (IgdbUnavailable, IgdbRateLimited):
        stale = _cache.get_stale(key)
        if stale is not None:
            logger.warning("IGDB fora do ar; servindo cópia em cache de %s", key[0])
            return stale
        raise
    _cache.set(key, value, ttl=current_app.config[ttl_name], stale_ttl=current_app.config["IGDB_STALE_TTL"])
    return value


def clear_cache() -> None:
    _cache.clear()


# ------------------------------------------------------------------ normalização
def image_url(image_id, size: str) -> str | None:
    """Endereço de uma imagem do IGDB (capa, captura de tela...) no tamanho pedido, ou None."""
    if not isinstance(image_id, str) or not _IMAGE_ID.match(image_id) or not re.match(r"^t_[a-z0-9_]+$", size):
        return None
    return f"{_IMAGE_HOST}/{size}/{image_id}.jpg"


_IMAGE_URL = re.compile(r"^" + re.escape(_IMAGE_HOST) + r"/t_[a-z0-9_]+/([A-Za-z0-9_-]{1,64})\.jpg$")


def thumb_url(cover: str | None) -> str | None:
    """A versão para cartões (264x374) de uma capa do IGDB já guardada; outras imagens ficam como estão."""
    if not cover:
        return None
    match = _IMAGE_URL.match(cover)
    return f"{_IMAGE_HOST}/t_cover_big/{match.group(1)}.jpg" if match else cover


def _image_of(item, size: str) -> str | None:
    return image_url(item.get("image_id"), size) if isinstance(item, dict) else None


def _names(items) -> list[str]:
    return [i["name"] for i in items or [] if isinstance(i, dict) and isinstance(i.get("name"), str) and i["name"]]


def _genre_name(item: dict) -> str | None:
    name = GENRE_NAMES.get(item.get("slug")) or item.get("name")
    return name if isinstance(name, str) and name else None


def _platform_id(item):
    if isinstance(item, dict):
        item = item.get("id")
    return item if isinstance(item, int) and not isinstance(item, bool) else None


def release_date(raw: dict) -> str | None:
    """A data de lançamento (AAAA-MM-DD, em UTC) a partir do carimbo de tempo do IGDB, ou None."""
    stamp = raw.get("first_release_date")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return None
    try:
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None
    return day.isoformat() if 1970 <= day.year <= 2200 else None


def safe_image_url(value) -> str | None:
    """Só aceita https (evita javascript:, data: e conteúdo misto)."""
    if not isinstance(value, str) or len(value) > 600:
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.netloc else None


def safe_web_url(value) -> str | None:
    if not isinstance(value, str) or len(value) > 500:
        return None
    parsed = urlparse(value.strip())
    return value.strip() if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _score(value, scale: int) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(min(float(value), 100.0) / (100 / scale), 2)


def normalize_summary(raw: dict) -> dict | None:
    igdb_id = raw.get("id")
    if not isinstance(igdb_id, int) or isinstance(igdb_id, bool):
        return None
    cover = raw.get("cover")
    critic = _score(raw.get("aggregated_rating"), 100)
    groups = {_GROUP_BY_PLATFORM[pid]["name"] for pid in map(_platform_id, raw.get("platforms") or []) if pid in _GROUP_BY_PLATFORM}
    return {
        "igdb_id": igdb_id,
        "name": str(raw.get("name") or "Sem título").strip(),
        "slug": str(raw.get("slug") or ""),
        "cover_url": _image_of(cover, "t_720p"),  # alta (prévias de links e topo da página)
        "cover_thumb_url": _image_of(cover, "t_cover_big"),  # 264x374, para os cartões
        "released": release_date(raw),
        "genres": [n for n in (_genre_name(g) for g in raw.get("genres") or [] if isinstance(g, dict)) if n],
        "platforms": [g["name"] for g in PLATFORM_GROUPS if g["name"] in groups],
        "critic_score": round(critic) if critic is not None else None,
    }


def _age_label(organization: str, rating: str) -> str:
    key = organization.lower()
    if key == "classind":
        return "Livre" if rating.upper() == "L" else f"{rating} anos"
    if key == "esrb":
        names = {"EC": "Early Childhood", "E": "Everyone", "E10+": "Everyone 10+", "T": "Teen", "M": "Mature 17+",
                 "AO": "Adults Only 18+", "RP": "Rating Pending"}
        return names.get(rating.upper(), rating)
    return f"{organization} {rating}"


def age_rating(raw: dict) -> dict | None:
    """A classificação etária a mostrar: a do Brasil (ClassInd) se houver, depois ESRB e PEGI, depois a primeira."""
    found = adult.age_ratings(raw)
    for preferred in ("classind", "esrb", "pegi"):
        for organization, rating in found:
            if organization.lower() == preferred:
                return {"label": _age_label(organization, rating), "organization": organization}
    if found:
        organization, rating = found[0]
        return {"label": _age_label(organization, rating), "organization": organization}
    return None


def _official_website(raw: dict) -> str | None:
    for item in raw.get("websites") or []:
        url = safe_web_url(item.get("url") if isinstance(item, dict) else None)
        if url and not any(host in (urlparse(url).netloc or "").lower() for host in _NOT_OFFICIAL):
            return url
    return None


def _companies(raw: dict, role: str) -> list[str]:
    names: list[str] = []
    for item in raw.get("involved_companies") or []:
        company = item.get("company") if isinstance(item, dict) else None
        if isinstance(item, dict) and item.get(role) and isinstance(company, dict) and company.get("name"):
            if company["name"] not in names:
                names.append(company["name"])
    return names


def normalize_detail(raw: dict) -> dict | None:
    base = normalize_summary(raw)
    if base is None:
        return None
    description = raw.get("summary") if isinstance(raw.get("summary"), str) else ""
    if not description.strip() and isinstance(raw.get("storyline"), str):
        description = raw["storyline"]
    description = re.sub(r"\n{3,}", "\n\n", strip_html(description).replace("\r", "")).strip()[:6000]
    shots = [u for u in (_image_of(s, "t_screenshot_big") for s in raw.get("screenshots") or []) if u]
    artworks = [u for u in (_image_of(a, "t_1080p") for a in raw.get("artworks") or []) if u]
    wide = next(iter(artworks), None) or next((u for u in (_image_of(s, "t_1080p") for s in raw.get("screenshots") or []) if u), None)
    count = raw.get("total_rating_count")
    base.update(
        {
            "name_original": None,
            "description": description,
            "cover_additional_url": wide,
            "developers": _companies(raw, "developer"),
            "publishers": _companies(raw, "publisher"),
            "platforms": _names(raw.get("platforms")) or base["platforms"],
            "website": _official_website(raw),
            "age_rating": age_rating(raw),
            "playtime": None,
            # Notas agregadas pelo próprio IGDB (de 0 a 10) — separadas da comunidade DiscPlayer.
            "igdb_rating": _score(raw.get("total_rating"), 10),
            "igdb_ratings_count": count if isinstance(count, int) and not isinstance(count, bool) else 0,
            "screenshots": shots[:6],
        }
    )
    return base


# ---------------------------------------------------------------------- consultas
_SUMMARY_FIELDS = (
    "name", "slug", "cover.image_id", "first_release_date", "genres.name", "genres.slug", "platforms.id",
    "aggregated_rating", "total_rating", "total_rating_count",
    "age_ratings.organization.name", "age_ratings.rating_category.rating", "themes.slug",
)
_DETAIL_FIELDS = _SUMMARY_FIELDS + (
    "summary", "storyline", "platforms.name", "screenshots.image_id", "artworks.image_id", "websites.url",
    "involved_companies.developer", "involved_companies.publisher", "involved_companies.company.name",
)
# Só jogos "principais": sem DLCs, expansões nem edições (que têm um jogo-pai).
_MAIN_GAMES = (("parent_game", "null", None), ("version_parent", "null", None))
_SEARCH_POOL = 100  # com busca e uma ordem própria, ordena-se localmente os 100 melhores resultados


def _timestamp(day) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def _now() -> int:
    """Agora, arredondado para a hora: filtros com "até agora" iguais dentro da hora deixam o cache valer."""
    return int(datetime.now(timezone.utc).timestamp()) // 3600 * 3600


def _normalize_listing(raw, total, page: int, page_size: int, offset: int) -> dict:
    level = adult.normalize_level(current_app.config.get("ADULT_CONTENT_FILTER"))
    found = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
    shown = [r for r in found if not adult.is_blocked(r, level)]
    results = [item for item in (normalize_summary(r) for r in shown) if item]
    # O IGDB conta os jogos escondidos no total. Só dá para descontar os desta página: é uma aproximação, mas evita
    # "40 jogos" acima de uma lista vazia quando alguém procura por algo que o filtro esconde.
    total = total if isinstance(total, int) and not isinstance(total, bool) else offset + len(found)
    return {
        "results": results,
        "count": max(len(results), total - (len(found) - len(shown))),
        "page": page,
        "page_size": page_size,
        "has_next": offset + len(found) < total,
        "has_previous": page > 1,
    }


def _count_of(data) -> int | None:
    return data.get("count") if isinstance(data, dict) and isinstance(data.get("count"), int) else None


def _fetch(filters: tuple, *, search, sort, limit: int, offset: int):
    """(resultados brutos, total) de uma consulta de jogos. O total vem de uma segunda chamada, a /count."""
    total = _count_of(fetch_json(Query("games", filters=filters, search=search, count=True)))
    return fetch_json(Query("games", _SUMMARY_FIELDS, filters, search, sort, limit, offset)), total


def _listing(filters: tuple, *, search=None, sort=None, page: int, page_size: int) -> dict:
    offset = (page - 1) * page_size
    raw, total = _fetch(filters, search=search, sort=sort, limit=page_size, offset=offset)
    return _normalize_listing(raw, total, page, page_size, offset)


def _local_sort(raw: list[dict], ordering: str) -> list[dict]:
    """Ordem própria para uma busca: o IGDB ordena a busca por relevância e não aceita `sort` junto com ela."""
    field, _, direction = (ORDERINGS[ordering] or "name asc").partition(" ")
    present = [r for r in raw if r.get(field) not in (None, "")]
    missing = [r for r in raw if r.get(field) in (None, "")]  # sem valor: sempre no fim
    present.sort(key=lambda r: str(r[field]).lower() if isinstance(r[field], str) else r[field], reverse=direction == "desc")
    return present + missing


def _sorted_search(filters: tuple, search: str, ordering: str, page: int, page_size: int) -> dict:
    raw, _ = _fetch(filters, search=search, sort=None, limit=_SEARCH_POOL, offset=0)
    pool = _local_sort([r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else [], ordering)
    start = (page - 1) * page_size
    return _normalize_listing(pool[start:start + page_size], len(pool), page, page_size, start)


def search_games(
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 24,
    genres: str | None = None,
    platforms: str | None = None,
    year: int | None = None,
    ordering: str = "relevance",
) -> dict:
    """Catálogo paginado. Os parâmetros já chegam validados pela rota."""
    asked = bool((search or "").strip())
    search = clean_search(search or "") or None
    if asked and not search:
        return _normalize_listing([], 0, page, page_size, 0)  # só aspas e pontuação: não há o que procurar
    filters: list[tuple] = list(_MAIN_GAMES)
    if genres:
        wanted = set(genres.split(","))
        ids = tuple(g["id"] for g in list_genres() if g["slug"] in wanted)
        if not ids:
            return _normalize_listing([], 0, page, page_size, 0)  # gênero que o IGDB não tem: nada a mostrar
        filters.append(("genres", "in", ids))
    if platforms:
        ids = tuple(pid for gid in platforms.split(",") if int(gid) in _GROUP_BY_ID for pid in _GROUP_BY_ID[int(gid)]["igdb_ids"])
        if not ids:
            return _normalize_listing([], 0, page, page_size, 0)
        filters.append(("platforms", "in", ids))
    if year:
        filters += [
            ("first_release_date", ">=", _timestamp(datetime(year, 1, 1))),
            ("first_release_date", "<=", _timestamp(datetime(year, 12, 31)) + 86399),
        ]
    if not search:
        filters.append(("cover", "notnull", None))  # sem busca, jogo sem capa é quase sempre cadastro vazio
    sort = ORDERINGS.get(ordering)
    if sort:
        field = sort.split(" ")[0]
        if ordering == "rating":
            filters.append(("total_rating_count", ">=", 5))  # uma nota só não faz de um jogo "o melhor"
        elif ordering == "critics":
            filters.append(("aggregated_rating_count", ">=", 3))
        else:
            filters.append((field, "notnull", None))
        if ordering == "released" and not year:
            filters.append(("first_release_date", "<=", _now()))  # sem jogos ainda não lançados
    wanted_filters = tuple(filters)
    if search and sort:
        key = ("list", search, wanted_filters, ordering, page, page_size)
        return _cached(key, "IGDB_TTL_SEARCH", lambda: _sorted_search(wanted_filters, search, ordering, page, page_size))
    key = ("list", search, wanted_filters, sort, page, page_size)
    return _cached(key, "IGDB_TTL_SEARCH", lambda: _listing(wanted_filters, search=search, sort=sort, page=page, page_size=page_size))


def featured_games(kind: str, page_size: int = 12) -> dict:
    """Listas curadas para a página inicial: 'popular' ou 'new'."""
    today = today_utc()
    filters = list(_MAIN_GAMES) + [("cover", "notnull", None)]
    if kind == "popular":
        filters += [("first_release_date", ">=", _timestamp(datetime(today.year - 1, 1, 1))), ("first_release_date", "<=", _now()),
                    ("total_rating_count", "notnull", None)]
        sort = "total_rating_count desc"
    elif kind == "new":
        start = today - timedelta(days=75)
        filters += [("first_release_date", ">=", _timestamp(start)), ("first_release_date", "<=", _now())]
        sort = "first_release_date desc"
    else:
        raise ValueError(kind)
    key = ("featured", kind, page_size, today.isoformat())
    return _cached(key, "IGDB_TTL_FEATURED", lambda: _listing(tuple(filters), sort=sort, page=1, page_size=page_size))


def get_game(igdb_id: int) -> dict:
    def load() -> dict:
        found = fetch_json(Query("games", _DETAIL_FIELDS, (("id", "=", igdb_id),), limit=1))
        raw = found[0] if isinstance(found, list) and found and isinstance(found[0], dict) else None
        if raw is None:
            raise IgdbNotFound()
        reason = adult.block_reason(raw, current_app.config.get("ADULT_CONTENT_FILTER"))
        if reason:
            logger.info("IGDB: jogo %s escondido pelo filtro de conteúdo adulto (%s)", igdb_id, reason)
            return {"blocked": True}  # fica no cache: quem insiste nesse endereço não gasta a cota do IGDB
        detail = normalize_detail(raw)
        if detail is None:
            raise IgdbUnavailable("O IGDB enviou uma resposta inesperada.")
        return detail

    detail = _cached(("game", igdb_id), "IGDB_TTL_DETAIL", load)
    if detail.get("blocked"):
        raise IgdbBlocked()
    return detail


def cached_game(igdb_id: int) -> dict | None:
    """O detalhe do jogo se ele já está no cache (mesmo expirado, dentro da tolerância). Nunca chama o IGDB."""
    detail = _cache.get_stale(("game", igdb_id))
    return None if detail is None or detail.get("blocked") else detail


def list_genres() -> list[dict]:
    def load() -> list[dict]:
        raw = fetch_json(Query("genres", ("name", "slug"), sort="name asc", limit=100))
        genres = []
        for item in raw if isinstance(raw, list) else []:
            if isinstance(item, dict) and isinstance(item.get("id"), int) and item.get("slug") and item.get("name"):
                genres.append({"id": item["id"], "name": _genre_name(item) or item["name"], "slug": item["slug"]})
        return sorted(genres, key=lambda g: g["name"].lower())

    return _cached(("genres",), "IGDB_TTL_LOOKUPS", load)


def list_platforms() -> list[dict]:
    """As famílias de plataformas (PC, PlayStation, Xbox, Nintendo...) para o filtro do catálogo. Não usa a rede."""
    return [{"id": g["id"], "name": g["name"], "slug": g["slug"]} for g in PLATFORM_GROUPS]
