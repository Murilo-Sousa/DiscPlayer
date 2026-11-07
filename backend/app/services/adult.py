"""Filtro de conteúdo adulto para os jogos que vêm do IGDB.

O IGDB não tem um parâmetro para excluir jogos 18+, então o filtro é feito aqui, depois da resposta, olhando dois
campos que o serviço envia em cada jogo, tanto nas listas quanto no detalhe:

- `age_ratings`: as classificações etárias (ESRB, PEGI, ClassInd, USK...), cada uma com a organização e a nota;
- `themes`: os temas do jogo. O tema "Erotic" marca jogos com conteúdo sexual explícito.

Três níveis, escolhidos em `ADULT_CONTENT_FILTER` (backend/.env):

- `explicit` (padrão): esconde o que é adulto de fato (ESRB *Adults Only*) e o que tem o tema "Erotic".
- `mature`: também esconde o que alguma organização classifica como 17+/18+ (ESRB *Mature*, PEGI 18, USK 18,
  ClassInd 18). Pega jogos comuns de violência, como The Witcher 3 ou Red Dead Redemption 2.
- `off`: não esconde nada.

Limites que não dá para resolver aqui: o IGDB é editado pela comunidade, e um jogo sem classificação e sem o tema
certo passa. O filtro reduz o conteúdo adulto, não substitui moderação.
"""
from __future__ import annotations

import re

EXPLICIT = "explicit"
MATURE = "mature"
OFF = "off"
LEVELS = (EXPLICIT, MATURE, OFF)
DEFAULT_LEVEL = EXPLICIT  # na dúvida, filtrar: um valor desconhecido nunca desliga o filtro

# Temas (slug) que sempre escondem o jogo, fora do nível "off".
_THEMES_ALWAYS = frozenset({"erotic"})

# Organização -> notas que escondem o jogo. A nota "18" aparece em várias organizações: sempre se confere o par.
_RATINGS_ALWAYS = {"esrb": frozenset({"ao"})}
_RATINGS_MATURE_LEVEL = {
    "esrb": frozenset({"m"}),
    "pegi": frozenset({"18"}),
    "usk": frozenset({"18"}),
    "classind": frozenset({"18"}),
    "cero": frozenset({"z"}),
    "grac": frozenset({"18+", "18"}),
    "acb": frozenset({"r 18+", "r18+", "rc"}),
}

# O formato antigo do IGDB usava números para a organização e para a nota (campos hoje descontinuados).
_LEGACY_ORGANIZATIONS = {1: "ESRB", 2: "PEGI", 3: "CERO", 4: "USK", 5: "GRAC", 6: "ClassInd", 7: "ACB"}
_LEGACY_RATINGS = {
    ("ESRB", 6): "RP", ("ESRB", 7): "EC", ("ESRB", 8): "E", ("ESRB", 9): "E10+", ("ESRB", 10): "T",
    ("ESRB", 11): "M", ("ESRB", 12): "AO",
    ("PEGI", 1): "3", ("PEGI", 2): "7", ("PEGI", 3): "12", ("PEGI", 4): "16", ("PEGI", 5): "18",
    ("CERO", 17): "Z", ("USK", 18): "0", ("USK", 19): "6", ("USK", 20): "12", ("USK", 21): "18",
    ("GRAC", 25): "18+", ("ClassInd", 27): "L", ("ClassInd", 28): "10", ("ClassInd", 29): "12",
    ("ClassInd", 30): "14", ("ClassInd", 31): "16", ("ClassInd", 32): "18",
    ("ACB", 37): "R 18+", ("ACB", 38): "RC",
}

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def normalize_level(value) -> str:
    """O nível pedido, ou o padrão quando o valor é vazio, desconhecido ou de outro tipo."""
    level = str(value or "").strip().lower()
    return level if level in LEVELS else DEFAULT_LEVEL


def _slug(item) -> str:
    """O slug de um objeto do IGDB (`{"slug", "name"}`); sem slug, deriva do nome."""
    if not isinstance(item, dict):
        return ""
    slug = item.get("slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip().lower()
    name = item.get("name")
    return _NON_SLUG.sub("-", name.lower()).strip("-") if isinstance(name, str) else ""


def age_ratings(raw) -> list[tuple[str, str]]:
    """As classificações do jogo como pares (organização, nota), por exemplo ("ClassInd", "18").

    Aceita o formato atual (`organization.name` e `rating_category.rating`) e o antigo (números). Dados que não se
    reconhece são ignorados, nunca levantam erro.
    """
    items = raw.get("age_ratings") if isinstance(raw, dict) else None
    found: list[tuple[str, str]] = []
    for item in items if isinstance(items, list) else ():
        if not isinstance(item, dict):
            continue
        organization = item.get("organization")
        organization = organization.get("name") if isinstance(organization, dict) else organization
        category = item.get("rating_category")
        rating = category.get("rating") if isinstance(category, dict) else None
        if isinstance(organization, int) and not isinstance(organization, bool):
            organization = _LEGACY_ORGANIZATIONS.get(organization)
        if rating is None and isinstance(item.get("rating"), int) and isinstance(item.get("category"), int):
            organization = organization or _LEGACY_ORGANIZATIONS.get(item["category"])
            rating = _LEGACY_RATINGS.get((organization, item["rating"]))
        if isinstance(organization, str) and isinstance(rating, str) and organization.strip() and rating.strip():
            found.append((organization.strip(), rating.strip()))
    return found


def block_reason(raw, level: str) -> str | None:
    """Por que o jogo (no formato bruto do IGDB) fica escondido nesse nível, ou None se pode aparecer."""
    level = normalize_level(level)
    if level == OFF or not isinstance(raw, dict):
        return None
    ratings = {key: set(values) for key, values in _RATINGS_ALWAYS.items()}
    themes = set(_THEMES_ALWAYS)
    if level == MATURE:
        for key, values in _RATINGS_MATURE_LEVEL.items():
            ratings.setdefault(key, set()).update(values)
    for organization, rating in age_ratings(raw):
        if rating.lower() in ratings.get(organization.lower(), ()):
            return f"classificação {organization} {rating}"
    found = raw.get("themes")
    for theme in found if isinstance(found, list) else ():
        slug = _slug(theme)
        if slug in themes:
            return f"tema {slug}"
    return None


def is_blocked(raw, level: str) -> bool:
    return block_reason(raw, level) is not None
