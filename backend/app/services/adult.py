"""Filtro de conteúdo adulto para os jogos que vêm da RAWG.

A RAWG não tem um parâmetro para excluir jogos 18+ (só `tags` para incluir), então o filtro é feito aqui, depois
da resposta, olhando dois campos que ela envia em cada jogo, tanto nas listas quanto no detalhe:

- `esrb_rating`: a classificação da ESRB (`adults-only` é o 18+ oficial; `mature` é 17+);
- `tags`: marcações da comunidade, vindas em boa parte da Steam (`nsfw`, `hentai`, `nudity`...).

Três níveis, escolhidos em `ADULT_CONTENT_FILTER` (backend/.env):

- `explicit` (padrão): esconde o que é 18+ de fato (ESRB *Adults Only*) e o que é marcado como explícito.
- `mature`: também esconde ESRB *Mature* (17+) e as tags de nudez e conteúdo sexual (pega GTA, The Witcher...).
- `off`: não esconde nada.

Limites que não dá para resolver aqui: a RAWG é editada pela comunidade, e muitos jogos adultos não têm
classificação nenhuma, então o filtro depende de eles estarem com as tags certas. Não substitui moderação.
"""
from __future__ import annotations

import re

EXPLICIT = "explicit"
MATURE = "mature"
OFF = "off"
LEVELS = (EXPLICIT, MATURE, OFF)
DEFAULT_LEVEL = EXPLICIT  # na dúvida, filtrar: um valor desconhecido nunca desliga o filtro

# Slugs da ESRB na RAWG: everyone, everyone-10-plus, teen, mature, adults-only, rating-pending.
_ESRB_ALWAYS = frozenset({"adults-only"})
_ESRB_MATURE_LEVEL = frozenset({"mature"})

# Slugs de tags da RAWG. Não é uma lista oficial: confira com a sua chave (veja docs/desenvolvimento.md).
_TAGS_ALWAYS = frozenset({"nsfw", "hentai", "eroge", "erotic"})
_TAGS_MATURE_LEVEL = frozenset({"sexual-content", "nudity"})  # a Steam as põe em muitos jogos 17+ comuns

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def normalize_level(value) -> str:
    """O nível pedido, ou o padrão quando o valor é vazio, desconhecido ou de outro tipo."""
    level = str(value or "").strip().lower()
    return level if level in LEVELS else DEFAULT_LEVEL


def _slug(item) -> str:
    """O slug de um objeto da RAWG (`{"slug", "name"}`); sem slug, deriva do nome."""
    if not isinstance(item, dict):
        return ""
    slug = item.get("slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip().lower()
    name = item.get("name")
    return _NON_SLUG.sub("-", name.lower()).strip("-") if isinstance(name, str) else ""


def block_reason(raw, level: str) -> str | None:
    """Por que o jogo (no formato bruto da RAWG) fica escondido nesse nível, ou None se pode aparecer."""
    level = normalize_level(level)
    if level == OFF or not isinstance(raw, dict):
        return None
    esrb_always, tags_always = _ESRB_ALWAYS, _TAGS_ALWAYS
    if level == MATURE:
        esrb_always, tags_always = esrb_always | _ESRB_MATURE_LEVEL, tags_always | _TAGS_MATURE_LEVEL
    esrb = _slug(raw.get("esrb_rating"))
    if esrb in esrb_always:
        return f"classificação {esrb}"
    tags = raw.get("tags")
    for tag in tags if isinstance(tags, list) else ():
        slug = _slug(tag)
        if slug in tags_always:
            return f"tag {slug}"
    return None


def is_blocked(raw, level: str) -> bool:
    return block_reason(raw, level) is not None
