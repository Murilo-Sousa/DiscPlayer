"""Integração com a RAWG Video Games Database API (https://api.rawg.io/docs/).

Só o back-end conversa com a RAWG: a chave fica em RAWG_API_KEY no servidor e
nunca chega ao navegador. As respostas são normalizadas para um formato próprio
do DiscPlayer (o front-end não depende do formato da RAWG) e nenhum campo é
tratado como garantido: quando a RAWG omite algo, o campo vem vazio.

Termos de uso: o plano gratuito exige um link visível de volta para a RAWG
(feito no rodapé e na página do jogo) e uso não comercial.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from urllib.parse import urlparse

import requests
from flask import current_app

from ..utils.cache import TTLCache
from ..utils.dates import parse_iso_date, today_utc
from ..utils.text import strip_html

logger = logging.getLogger(__name__)

_session = requests.Session()
_cache = TTLCache(max_entries=1500)

# Ordenações oferecidas ao usuário -> parâmetro `ordering` da RAWG.
ORDERINGS: dict[str, str | None] = {
    "relevance": None,  # relevância da própria busca
    "popular": "-added",
    "released": "-released",
    "rating": "-rating",
    "metacritic": "-metacritic",
    "name": "name",
}


# ------------------------------------------------------------------------- erros
class RawgError(Exception):
    status = 502
    code = "rawg_error"
    message = "Não foi possível consultar a RAWG."

    def __init__(self, message: str | None = None, retry_after: int | None = None):
        self.message = message or self.message
        self.retry_after = retry_after
        super().__init__(self.message)


class RawgNotConfigured(RawgError):
    status = 503
    code = "rawg_not_configured"
    message = (
        "A integração com a RAWG não está configurada. "
        "Defina RAWG_API_KEY no arquivo backend/.env e reinicie o servidor."
    )


class RawgNotFound(RawgError):
    status = 404
    code = "game_not_found"
    message = "Jogo não encontrado na RAWG."


class RawgRateLimited(RawgError):
    status = 429
    code = "rawg_rate_limited"
    message = "O limite de consultas à RAWG foi atingido. Tente novamente em alguns minutos."


class RawgUnavailable(RawgError):
    status = 503
    code = "rawg_unavailable"
    message = "A RAWG está indisponível no momento. Tente novamente em instantes."


# --------------------------------------------------------------------- transporte
def fetch_json(path: str, params: dict | None = None) -> dict | list:
    """GET na RAWG. É o único ponto de rede do módulo (os testes o substituem)."""
    config = current_app.config
    key = config["RAWG_API_KEY"]
    if not key:
        raise RawgNotConfigured()
    url = f"{config['RAWG_BASE_URL']}/{path.lstrip('/')}"
    query = {**(params or {}), "key": key}
    try:
        response = _session.get(
            url,
            params=query,
            timeout=config["RAWG_TIMEOUT"],
            headers={"Accept": "application/json", "User-Agent": "DiscPlayer/1.0"},
        )
    except requests.Timeout:
        logger.warning("RAWG: timeout em /%s", path.lstrip("/"))
        raise RawgUnavailable("A RAWG demorou demais para responder. Tente novamente.") from None
    except requests.RequestException as exc:
        # Não registramos a mensagem da exceção: ela costuma conter a URL com a chave.
        logger.warning("RAWG: falha de conexão em /%s (%s)", path.lstrip("/"), type(exc).__name__)
        raise RawgUnavailable() from None

    status = response.status_code
    if status == 404:
        raise RawgNotFound()
    if status in (401, 403):
        logger.error("RAWG recusou a chave de API (HTTP %s)", status)
        raise RawgNotConfigured("A RAWG recusou a chave de API. Confira o valor de RAWG_API_KEY.")
    if status == 429:
        retry = response.headers.get("Retry-After", "")
        raise RawgRateLimited(retry_after=int(retry) if retry.isdigit() else None)
    if status != 200:
        logger.warning("RAWG: HTTP %s em /%s", status, path.lstrip("/"))
        raise RawgUnavailable()
    try:
        return response.json()
    except ValueError:
        logger.warning("RAWG: resposta que não é JSON em /%s", path.lstrip("/"))
        raise RawgUnavailable("A RAWG enviou uma resposta inesperada.") from None


def _cached(key: tuple, ttl_name: str, loader):
    """Cache com tolerância a falhas: se a RAWG cair, usa o último valor guardado."""
    hit = _cache.get(key)
    if hit is not None:
        return hit
    try:
        value = loader()
    except (RawgUnavailable, RawgRateLimited):
        stale = _cache.get_stale(key)
        if stale is not None:
            logger.warning("RAWG fora do ar; servindo cópia em cache de %s", key[0])
            return stale
        raise
    _cache.set(key, value, ttl=current_app.config[ttl_name], stale_ttl=current_app.config["RAWG_STALE_TTL"])
    return value


def clear_cache() -> None:
    _cache.clear()


# ------------------------------------------------------------------ normalização
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


_MEDIA_RE = re.compile(r"^https://media\.rawg\.io/media/(games/.+)$")


def thumb_url(cover: str | None) -> str | None:
    """Versão 600x400 da imagem (a RAWG serve recortes em /media/crop/L/A/).

    Se o recorte não existir, o front-end cai de volta para `cover_url`.
    """
    if not cover:
        return None
    match = _MEDIA_RE.match(cover)
    return f"https://media.rawg.io/media/crop/600/400/{match.group(1)}" if match else cover


def _names(items) -> list[str]:
    return [i["name"] for i in items or [] if isinstance(i, dict) and i.get("name")]


def _platform_names(items) -> list[str]:
    names = []
    for item in items or []:
        platform = item.get("platform") if isinstance(item, dict) else None
        if isinstance(platform, dict) and platform.get("name"):
            names.append(platform["name"])
    return names


def normalize_summary(raw: dict) -> dict | None:
    rawg_id = raw.get("id")
    if not isinstance(rawg_id, int) or isinstance(rawg_id, bool):
        return None
    cover = safe_image_url(raw.get("background_image"))
    released = raw.get("released")
    metacritic = raw.get("metacritic")
    return {
        "rawg_id": rawg_id,
        "name": str(raw.get("name") or "Sem título").strip(),
        "slug": str(raw.get("slug") or ""),
        "cover_url": cover,
        "cover_thumb_url": thumb_url(cover),
        "released": released if parse_iso_date(released) else None,
        "genres": _names(raw.get("genres")),
        "platforms": _platform_names(raw.get("parent_platforms")),
        "metacritic": metacritic if isinstance(metacritic, int) else None,
    }


def normalize_detail(raw: dict) -> dict | None:
    base = normalize_summary(raw)
    if base is None:
        return None
    description = raw.get("description_raw")
    if not isinstance(description, str) or not description.strip():
        description = strip_html(raw.get("description"))
    description = re.sub(r"\n{3,}", "\n\n", description.replace("\r", "")).strip()[:6000]
    rating = raw.get("rating")
    base.update(
        {
            "name_original": raw.get("name_original") or None,
            "description": description,
            "cover_additional_url": safe_image_url(raw.get("background_image_additional")),
            "developers": _names(raw.get("developers")),
            "publishers": _names(raw.get("publishers")),
            "platforms": _platform_names(raw.get("platforms")) or base["platforms"],
            "website": safe_web_url(raw.get("website")),
            "esrb": (raw.get("esrb_rating") or {}).get("name") if isinstance(raw.get("esrb_rating"), dict) else None,
            "playtime": raw.get("playtime") if isinstance(raw.get("playtime"), int) and raw["playtime"] > 0 else None,
            # Notas agregadas pela própria RAWG — separadas da comunidade DiscPlayer.
            "rawg_rating": float(rating) if isinstance(rating, (int, float)) and rating > 0 else None,
            "rawg_ratings_count": raw.get("ratings_count") if isinstance(raw.get("ratings_count"), int) else 0,
        }
    )
    return base


def _normalize_listing(raw: dict, page: int, page_size: int) -> dict:
    results = [item for item in (normalize_summary(r) for r in raw.get("results") or []) if item]
    return {
        "results": results,
        "count": raw.get("count") if isinstance(raw.get("count"), int) else len(results),
        "page": page,
        "page_size": page_size,
        "has_next": bool(raw.get("next")),
        "has_previous": bool(raw.get("previous")),
    }


# ---------------------------------------------------------------------- consultas
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
    params: dict = {"page": page, "page_size": page_size, "exclude_additions": "true"}
    if search:
        params["search"] = search
    if genres:
        params["genres"] = genres
    if platforms:
        params["parent_platforms"] = platforms
    if year:
        params["dates"] = f"{year}-01-01,{year}-12-31"
    rawg_ordering = ORDERINGS.get(ordering)
    if rawg_ordering:
        params["ordering"] = rawg_ordering
        if ordering == "released" and not year:
            params["dates"] = f"1970-01-01,{today_utc().isoformat()}"  # sem jogos ainda não lançados
    ttl = "RAWG_TTL_SEARCH"
    key = ("list", tuple(sorted(params.items())))
    return _cached(key, ttl, lambda: _normalize_listing(fetch_json("games", params), page, page_size))


def featured_games(kind: str, page_size: int = 12) -> dict:
    """Listas curadas para a página inicial: 'popular' ou 'new'."""
    today = today_utc()
    params: dict = {"page": 1, "page_size": page_size, "exclude_additions": "true"}
    if kind == "popular":
        params.update(ordering="-added", dates=f"{today.year - 1}-01-01,{today.isoformat()}")
    elif kind == "new":
        params.update(ordering="-released", dates=f"{(today - timedelta(days=75)).isoformat()},{today.isoformat()}")
    else:
        raise ValueError(kind)
    key = ("featured", kind, page_size, today.isoformat())
    return _cached(key, "RAWG_TTL_FEATURED", lambda: _normalize_listing(fetch_json("games", params), 1, page_size))


def get_game(rawg_id: int) -> dict:
    def load() -> dict:
        detail = normalize_detail(fetch_json(f"games/{rawg_id}"))  # type: ignore[arg-type]
        if detail is None:
            raise RawgUnavailable("A RAWG enviou uma resposta inesperada.")
        return detail

    return _cached(("game", rawg_id), "RAWG_TTL_DETAIL", load)


def cached_game(rawg_id: int) -> dict | None:
    """O detalhe do jogo se ele já está no cache (mesmo expirado, dentro da tolerância). Nunca chama a RAWG."""
    return _cache.get_stale(("game", rawg_id))


def get_screenshots(rawg_id: int, limit: int = 6) -> list[str]:
    """Imagens extras do jogo. Falhas aqui nunca derrubam a página do jogo."""

    def load() -> list[str]:
        raw = fetch_json(f"games/{rawg_id}/screenshots", {"page_size": limit})
        urls = [safe_image_url(item.get("image")) for item in raw.get("results") or [] if isinstance(item, dict)]  # type: ignore[union-attr]
        return [u for u in urls if u][:limit]

    try:
        return _cached(("shots", rawg_id, limit), "RAWG_TTL_DETAIL", load)
    except RawgError:
        return []


def list_genres() -> list[dict]:
    def load() -> list[dict]:
        raw = fetch_json("genres", {"ordering": "name", "page_size": 40})
        return [
            {"id": g["id"], "name": g["name"], "slug": g["slug"]}
            for g in raw.get("results") or []  # type: ignore[union-attr]
            if isinstance(g, dict) and g.get("id") and g.get("name") and g.get("slug")
        ]

    return _cached(("genres",), "RAWG_TTL_LOOKUPS", load)


def list_platforms() -> list[dict]:
    """Plataformas-pai (PC, PlayStation, Xbox, Nintendo...) para o filtro do catálogo."""

    def load() -> list[dict]:
        raw = fetch_json("platforms/lists/parents")
        return [
            {"id": p["id"], "name": p["name"], "slug": p.get("slug", "")}
            for p in raw.get("results") or []  # type: ignore[union-attr]
            if isinstance(p, dict) and p.get("id") and p.get("name")
        ]

    return _cached(("platforms",), "RAWG_TTL_LOOKUPS", load)
