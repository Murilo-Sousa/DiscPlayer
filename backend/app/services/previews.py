"""Prévia de links: título, descrição e imagem que aparecem ao colar um endereço do site em outro app.

Os robôs do WhatsApp, do Discord, do LinkedIn etc. não executam JavaScript, então estas informações
precisam estar no HTML que o servidor entrega. `for_path` devolve a prévia certa para cada endereço
do site; `spa.py` a coloca no `index.html`.

Regras:
  * só entra o que já é público (perfil, jogo, lista PÚBLICA, retrospectiva); lista privada e
    qualquer coisa que não exista caem na prévia padrão do site, sem revelar nada;
  * nunca levanta erro: se algo falhar (banco), a prévia padrão é usada e a página abre normal;
  * nunca chama a RAWG: um jogo que ninguém registrou usa o cache dela (que a própria página do jogo
    preenche ao abrir) e, sem cache, cai na prévia padrão. Assim um robô que percorre endereços de jogos
    não gasta a cota da RAWG nem deixa a página lenta;
  * não há texto de review nem e-mail na prévia;
  * todo texto é escapado na hora de virar HTML (veja `spa.py`), então nome, bio e título de lista
    com aspas ou `<` não quebram a página.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

from . import cards, rawg
from . import games as games_service
from . import lists as lists_service
from . import profiles as profiles_service
from . import retrospective as retrospective_service
from . import reviews as reviews_service

logger = logging.getLogger(__name__)

SITE_NAME = "DiscPlayer"
DEFAULT_DESCRIPTION = (
    "DiscPlayer é o diário de videogames: registre o que você joga, avalie, escreva reviews e monte listas."
)
DEFAULT_IMAGE_ALT = "O logotipo do DiscPlayer: um disco com um quarto preenchido."
DESCRIPTION_LIMIT = 200
TITLE_LIMIT = 110

# [0-9] (e não \d): em Python, \d também casa dígitos de outros alfabetos, que não são endereços do site.
_GAME = re.compile(r"^jogos/([0-9]{1,9})(?:-[^/]*)?/?$")
_PROFILE = re.compile(r"^u/([A-Za-z0-9_]{3,24})/?$")
_RETRO = re.compile(r"^u/([A-Za-z0-9_]{3,24})/retrospectiva(?:/([0-9]{4}))?/?$")
_LIST = re.compile(r"^listas/([0-9]{1,9})/?$")


@dataclass(frozen=True)
class Preview:
    title: str
    description: str
    image: str | None
    image_alt: str = ""
    # "summary_large_image" (imagem larga: capa, cartão) ou "summary" (imagem quadrada)
    card: str = "summary_large_image"
    # as imagens geradas por nós têm tamanho conhecido
    image_size: tuple[int, int] | None = None


# Cola de emoji compostos (família, bandeiras): é "invisível" para isprintable, mas sem ela o emoji se desfaz.
_JOINERS = {"\u200d", "\u200c"}


def _clean(text: str | None, limit: int) -> str:
    """Uma linha, sem caracteres de controle, cortada no limite."""
    flat = " ".join("".join(ch if ch.isprintable() or ch in _JOINERS else " " for ch in (text or "")).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _number(value: float | None) -> str:
    """Até duas casas, sem zeros à direita, com vírgula (8,25; 9; 7,5): igual ao que a página mostra."""
    if value is None:
        return ""
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def default_preview(base: str) -> Preview:
    return Preview(
        title=SITE_NAME,
        description=DEFAULT_DESCRIPTION,
        image=_card_url(base, "default.png"),
        image_alt=DEFAULT_IMAGE_ALT,
        image_size=(cards.WIDTH, cards.HEIGHT),
    )


def _card_url(base: str, path: str) -> str | None:
    if not cards.available():
        return None
    return f"{base}/api/share/{path}"


# --------------------------------------------------------------------------- jogo
def _game_preview(rawg_id: int, base: str) -> Preview | None:
    local = games_service.get_local_game(rawg_id)
    if local is not None:
        name, cover, released = local["name"], local["cover_url"], local["release_date"]
    else:
        detail = rawg.cached_game(rawg_id)  # só o cache: aqui a RAWG nunca é chamada
        if detail is None:
            return None
        name, cover, released = detail["name"], detail.get("cover_url"), detail.get("released")

    parts = []
    if released and len(released) >= 4:
        parts.append(f"Lançado em {released[:4]}.")
    community = reviews_service.community_stats(local["id"]) if local is not None else None
    if community and community["count"]:
        parts.append(
            f"Nota média da comunidade DiscPlayer: {_number(community['average'])} em {community['count']} "
            f"{_plural(community['count'], 'avaliação', 'avaliações')}."
        )
    else:
        parts.append(f"Registre, avalie e escreva sobre {name} no DiscPlayer.")
    cover_url = rawg.safe_image_url(cover)
    return Preview(
        title=_clean(f"{name} · {SITE_NAME}", TITLE_LIMIT),
        description=_clean(" ".join(parts), DESCRIPTION_LIMIT),
        image=cover_url or _card_url(base, "default.png"),
        image_alt=_clean(f"Capa de {name}", 120) if cover_url else DEFAULT_IMAGE_ALT,
        image_size=None if cover_url else (cards.WIDTH, cards.HEIGHT),
    )


# --------------------------------------------------------------------------- perfil
def _profile_preview(username: str, base: str) -> Preview | None:
    user = profiles_service.get_by_username(username)
    if user is None:
        return None
    stats = profiles_service.stats_for(user["id"], include_private_lists=False)
    facts = []
    if stats["games"]:
        facts.append(f"{stats['games']} {_plural(stats['games'], 'jogo', 'jogos')} no diário")
    zeradas = stats["by_status"]["zerado"]
    if zeradas:
        facts.append(f"{zeradas} {_plural(zeradas, 'zerado', 'zerados')}")
    if stats["average_rating"] is not None:
        facts.append(f"nota média {_number(stats['average_rating'])}")
    summary = " · ".join(facts) if facts else f"{user['display_name']} está no DiscPlayer."
    bio = _clean(user["bio"], 120)
    description = f"{summary}. {bio}" if facts and bio else (summary if facts else f"{summary} {bio}".strip())
    return Preview(
        title=_clean(f"{user['display_name']} (@{user['username']}) · {SITE_NAME}", TITLE_LIMIT),
        description=_clean(description, DESCRIPTION_LIMIT),
        image=_card_url(base, f"profile/{quote(user['username'])}.png"),
        image_alt=_clean(f"Perfil de {user['display_name']} no DiscPlayer", 120),
        image_size=(cards.WIDTH, cards.HEIGHT),
    )


# --------------------------------------------------------------------------- retrospectiva
def _retrospective_preview(username: str, year_text: str | None, base: str) -> Preview | None:
    user = profiles_service.get_by_username(username)
    if user is None:
        return None
    if year_text is None:
        year = retrospective_service.default_year(user["id"])
    else:
        year = int(year_text)
        if not retrospective_service.is_valid_year(year):
            return None
    data = retrospective_service.build(user, year)
    if data["empty"]:
        return _profile_preview(username, base)  # sem dados no ano: a prévia é a do perfil
    totals, best = data["totals"], data["game_of_the_year"]
    facts = []
    if totals["completed"]:
        facts.append(f"{totals['completed']} {_plural(totals['completed'], 'jogo zerado', 'jogos zerados')}")
    if totals["started"]:
        facts.append(f"{totals['started']} {_plural(totals['started'], 'começado', 'começados')}")
    if data["ratings"]["average"] is not None:
        facts.append(f"nota média {_number(data['ratings']['average'])}")
    if best:
        facts.append(f"jogo do ano: {best['game']['name']}")
    suffix = " (até agora)" if data["partial"] else ""
    return Preview(
        title=_clean(f"Retrospectiva {year}{suffix} de {user['display_name']} · {SITE_NAME}", TITLE_LIMIT),
        description=_clean(" · ".join(facts) or f"A retrospectiva de {year} no DiscPlayer.", DESCRIPTION_LIMIT),
        image=_card_url(base, f"retrospective/{quote(user['username'])}/{year}.png"),
        image_alt=_clean(f"Retrospectiva {year} de {user['display_name']}", 120),
        image_size=(cards.WIDTH, cards.HEIGHT),
    )


# --------------------------------------------------------------------------- lista
def _list_preview(list_id: int, base: str) -> Preview | None:
    row = lists_service.get_visible(list_id, None)  # sem viewer: lista privada = inexistente
    if row is None:
        return None
    count = row["game_count"]
    description = _clean(row["description"], 140) or (
        f"{count} {_plural(count, 'jogo', 'jogos')} nesta lista." if count else "Uma lista de jogos."
    )
    description = _clean(f"Lista de {row['display_name']}. {description}", DESCRIPTION_LIMIT)
    first = lists_service.covers_for([list_id], per_list=1).get(list_id) or []
    cover = rawg.safe_image_url(first[0]["cover_url"]) if first else None
    return Preview(
        title=_clean(f"{row['title']} · lista de {row['display_name']} · {SITE_NAME}", TITLE_LIMIT),
        description=description,
        image=cover or _card_url(base, "default.png"),
        image_alt=_clean(f"Capa de {first[0]['name']}", 120) if cover else DEFAULT_IMAGE_ALT,
        image_size=None if cover else (cards.WIDTH, cards.HEIGHT),
    )


# --------------------------------------------------------------------------- entrada
def is_dynamic(path: str) -> bool:
    """True para os endereços cuja prévia depende do banco (jogo, perfil, retrospectiva, lista)."""
    path = path.strip("/")
    return bool(_GAME.match(path) or _PROFILE.match(path) or _RETRO.match(path) or _LIST.match(path))


def for_path(path: str, base: str) -> Preview:
    """A prévia do endereço (`path` sem a barra inicial). Nunca levanta erro."""
    clean = path.strip("/")
    try:
        found: Preview | None = None
        if match := _GAME.match(clean):
            found = _game_preview(int(match.group(1)), base)
        elif match := _RETRO.match(clean):
            found = _retrospective_preview(match.group(1), match.group(2), base)
        elif match := _PROFILE.match(clean):
            found = _profile_preview(match.group(1), base)
        elif match := _LIST.match(clean):
            found = _list_preview(int(match.group(1)), base)
        if found is not None:
            return found
    except Exception:  # noqa: BLE001 - a prévia nunca pode derrubar a página
        logger.warning("Não foi possível montar a prévia de /%s", clean, exc_info=True)
    return default_preview(base)
