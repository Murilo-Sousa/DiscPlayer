"""Imagens de compartilhamento (1200 x 630), desenhadas no servidor com o Pillow.

São as imagens que aparecem quando alguém cola um link de perfil ou de retrospectiva no
WhatsApp, no Discord, no LinkedIn etc. Usam as cores e as fontes do próprio site
(TeX Gyre Adventor e Lora, de `frontend/src/assets/fonts`) e o motivo do disco.

Regras que valem para todas:
  * só desenham dados que já são públicos no perfil (nada de e-mail, listas privadas nem texto de review);
  * texto de pessoas só entra se a fonte tiver todos os caracteres (senão, aparece o @usuário);
    é por isso que um nome com emoji ou com outro alfabeto vira "@usuario" na imagem;
  * nenhuma imagem de fora é baixada: a foto do perfil vem do próprio banco.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache
from pathlib import Path

from ..config import PROJECT_DIR
from ..errors import ApiError

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1200, 630
_SCALE = 2  # desenha em dobro e reduz: as bordas ficam suaves

BG = (19, 19, 22)
SURFACE = (26, 26, 31)
SURFACE_3 = (43, 43, 51)
LINE = (45, 45, 54)
TEXT = (240, 239, 235)
TEXT_2 = (186, 185, 195)
TEXT_3 = (143, 142, 154)
ACCENT = (229, 210, 91)
ACCENT_INK = (28, 25, 7)

FONT_DIR = PROJECT_DIR / "frontend" / "src" / "assets" / "fonts"
_FONTS = {"ui": "adventor-regular.woff", "ui-bold": "adventor-bold.woff", "read": "lora-variable.woff"}

MONTH_LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def available() -> bool:
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        return False
    return True


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ApiError(
            503,
            "image_support_missing",
            "A geração de imagens está indisponível: falta instalar o Pillow no servidor.",
        ) from exc
    return Image, ImageDraw, ImageFont


@lru_cache(maxsize=64)
def _font(name: str, size: int):
    _, _, ImageFont = _pil()
    path: Path = FONT_DIR / _FONTS[name]
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:  # fonte ausente (pasta src não publicada): usa a fonte embutida do Pillow
        logger.warning("Fonte %s não encontrada; usando a fonte padrão do Pillow", path)
        return ImageFont.load_default(size)


@lru_cache(maxsize=None)
def _has_glyph(ch: str) -> bool:
    """True se as três fontes do site desenham `ch`.

    Um caractere ausente sai como o glifo de "caractere não encontrado"; então basta compará-lo com o
    desenho de um código que nenhuma fonte tem (U+FFFF). Vale para as fontes que realmente estão em uso
    (inclusive a fonte de reserva do Pillow, se os arquivos faltarem).
    """
    try:
        for name in _FONTS:
            font = _font(name, 40)
            if bytes(font.getmask(ch)) == bytes(font.getmask("\uffff")):
                return False
    except Exception:  # noqa: BLE001 - se não dá para conferir, trata como ausente (cai no @usuário)
        return False
    return True


def supported(text: str | None) -> bool:
    """True se as fontes desenham todos os caracteres (sem emoji, controle nem alfabetos que elas não cobrem).

    Espaços, tabulações e quebras de linha valem como um espaço só.
    """
    flat = " ".join((text or "").split())
    if not flat:
        return False
    return all(ch == " " or (ch.isprintable() and _has_glyph(ch)) for ch in flat)


def _fit(draw, text: str, name: str, size: int, max_width: int, min_size: int = 20):
    """Maior fonte (de `size` até `min_size`) em que o texto cabe; se nem a menor couber, corta com reticências."""
    for current in range(size, min_size - 1, -2):
        font = _font(name, current * _SCALE)
        if draw.textlength(text, font=font) <= max_width * _SCALE:
            return font, text
    font = _font(name, min_size * _SCALE)
    return font, _ellipsize(draw, text, font, max_width)


def _ellipsize(draw, text: str, font, max_width: int) -> str:
    """O começo de `text` que cabe em `max_width` (px), seguido de "…"."""
    cut = text.rstrip("…")
    while len(cut) > 1 and draw.textlength(cut + "…", font=font) > max_width * _SCALE:
        cut = cut[:-1]
    return cut.rstrip() + "…"


def _wrap(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Quebra `text` em até `max_lines` linhas que cabem em `max_width`; o que sobra vira "…" na última.

    Uma palavra maior que a linha (um endereço, por exemplo) é cortada com "…" em vez de sair da imagem.
    """
    limit = max_width * _SCALE
    lines: list[str] = []
    current = ""
    for word in text.split():
        if draw.textlength(word, font=font) > limit:
            word = _ellipsize(draw, word, font, max_width)
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= limit:
            current = trial
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(draw, lines[-1], font, max_width)
    return lines


def _canvas():
    Image, ImageDraw, _ = _pil()
    image = Image.new("RGB", (WIDTH * _SCALE, HEIGHT * _SCALE), BG)
    return image, ImageDraw.Draw(image)


def _px(value: float) -> int:
    return int(round(value * _SCALE))


def _text(draw, xy, text, font, fill, anchor="la"):
    draw.text((_px(xy[0]), _px(xy[1])), text, font=font, fill=fill, anchor=anchor)


def _disc(draw, cx: float, cy: float, size: float, *, color=TEXT, fill_color=ACCENT, bg=BG, quarters: int = 1):
    """O disco do logotipo: anel, quartos preenchidos (sentido horário, a partir das 12h) e o furo."""
    unit = size / 24
    outer, ring_w = 10.4 * unit, max(1.6 * unit, 1.0)
    draw.ellipse([_px(cx - outer), _px(cy - outer), _px(cx + outer), _px(cy + outer)], outline=color, width=_px(ring_w))
    band = 8.6 * unit
    for index in range(max(0, min(4, quarters))):
        start = -90 + 90 * index
        draw.pieslice(
            [_px(cx - band), _px(cy - band), _px(cx + band), _px(cy + band)], start, start + 90, fill=fill_color
        )
    hole = 3.4 * unit
    draw.ellipse([_px(cx - hole), _px(cy - hole), _px(cx + hole), _px(cy + hole)], fill=bg, outline=TEXT_3, width=_px(max(1.1 * unit, 1.0)))


def _brand(draw, x: float, y: float, *, size: float = 40):
    """Disco + "DiscPlayer", com o canto superior esquerdo em (x, y)."""
    _disc(draw, x + size / 2, y + size / 2, size)
    _text(draw, (x + size + 14, y + size / 2), "DiscPlayer", _font("ui-bold", _px(size * 0.62)), TEXT, "lm")


def _finish(image) -> bytes:
    Image, _, _ = _pil()
    out = io.BytesIO()
    image.resize((WIDTH, HEIGHT), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def _pt_number(value: float | None) -> str:
    """Até duas casas, sem zeros à direita, com vírgula (8,25; 9; 7,5): igual ao que a página mostra."""
    if value is None:
        return "–"
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _accent_rule(draw, x, y, width=64):
    draw.rectangle([_px(x), _px(y), _px(x + width), _px(y + 6)], fill=ACCENT)


# --------------------------------------------------------------------------- cartões
def default_card() -> bytes:
    """Cartão do site, usado em qualquer link que não tenha uma imagem melhor."""
    image, draw = _canvas()
    _disc(draw, 330, 315, 300, quarters=1)
    _text(draw, (560, 270), "DiscPlayer", _font("ui-bold", _px(92)), TEXT, "lm")
    _accent_rule(draw, 563, 335)
    tagline = _font("read", _px(36))
    for index, line in enumerate(("O diário e a comunidade", "dos seus jogos.")):
        _text(draw, (563, 392 + index * 50), line, tagline, TEXT_2, "lm")
    return _finish(image)


def _avatar_image(avatar_bytes: bytes | None, diameter: int):
    """A foto (já reprocessada pelo próprio servidor) recortada em círculo, ou None se não houver/for ilegível."""
    if not avatar_bytes:
        return None
    Image, ImageDraw, _ = _pil()
    try:
        photo = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((diameter, diameter), Image.LANCZOS)
    except Exception:  # noqa: BLE001 - qualquer problema com a foto vira "sem foto"
        return None
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter - 1, diameter - 1], fill=255)
    return photo, mask


def _draw_avatar(image, draw, cx, cy, diameter, *, avatar_bytes, display_name, username):
    px = _px(diameter)
    prepared = _avatar_image(avatar_bytes, px)
    left, top = _px(cx) - px // 2, _px(cy) - px // 2
    if prepared is not None:
        photo, mask = prepared
        image.paste(photo, (left, top), mask)
    else:
        draw.ellipse([left, top, left + px, top + px], fill=SURFACE_3)
        letters = "".join(word[0] for word in display_name.split()[:2]) if supported(display_name) else username[:1]
        _text(draw, (cx, cy), (letters or username[:1]).upper(), _font("ui-bold", _px(diameter * 0.38)), ACCENT, "mm")
    draw.ellipse([left, top, left + px, top + px], outline=LINE, width=_px(3))


def _display(name: str, username: str) -> str:
    return name if supported(name) else f"@{username}"


def profile_card(*, display_name: str, username: str, bio: str | None, stats: dict, avatar_bytes: bytes | None) -> bytes:
    image, draw = _canvas()
    _draw_avatar(image, draw, 210, 270, 260, avatar_bytes=avatar_bytes, display_name=display_name, username=username)

    left, width = 380, 760
    name = _display(display_name, username)
    font, shown = _fit(draw, name, "ui-bold", 68, width, 34)
    _text(draw, (left, 190), shown, font, TEXT, "ls")
    _text(draw, (left, 236), f"@{username}", _font("ui", _px(30)), TEXT_3, "ls")
    _accent_rule(draw, left + 3, 262)

    if bio and supported(bio):
        lines = _wrap(draw, bio, _font("read", _px(28)), width, 2)
        for index, line in enumerate(lines):
            _text(draw, (left, 322 + index * 40), line, _font("read", _px(28)), TEXT_2, "ls")

    cells = []
    if stats.get("games"):
        cells.append((str(stats["games"]), _plural(stats["games"], "jogo no diário", "jogos no diário")))
    if stats.get("by_status", {}).get("zerado"):
        total = stats["by_status"]["zerado"]
        cells.append((str(total), _plural(total, "zerado", "zerados")))
    if stats.get("average_rating") is not None:
        cells.append((_pt_number(stats["average_rating"]), "nota média"))
    for index, (value, label) in enumerate(cells[:3]):
        x = left + index * 250
        _text(draw, (x, 470), value, _font("ui-bold", _px(56)), ACCENT, "ls")
        _text(draw, (x, 508), label, _font("ui", _px(24)), TEXT_2, "ls")

    _brand(draw, 70, 540, size=40)
    return _finish(image)


def _month_bars(draw, values: list[int], x: float, y: float, width: float, height: float) -> None:
    """Doze barras (jan–dez) que sempre mostram o tamanho real; o mês mais cheio é o único em destaque."""
    top = max(values) if values else 0
    gap = 10
    bar_w = (width - gap * 11) / 12
    label_font = _font("ui", _px(20))
    for index in range(12):
        value = values[index] if index < len(values) else 0
        left = x + index * (bar_w + gap)
        bar_h = (height - 34) * (value / top) if top else 0
        base = y + height - 34
        draw.rectangle([_px(left), _px(base - 4), _px(left + bar_w), _px(base)], fill=SURFACE_3)  # base sempre visível
        if value:
            draw.rectangle(
                [_px(left), _px(base - max(bar_h, 4)), _px(left + bar_w), _px(base)],
                fill=ACCENT if value == top else TEXT_3,
            )
        _text(draw, (left + bar_w / 2, y + height - 10), MONTH_LETTERS[index], label_font, TEXT_3, "mm")


def retrospective_card(data: dict, *, avatar_bytes: bytes | None = None) -> bytes:
    """Cartão da retrospectiva. `data` é o resultado de `retrospective.build`."""
    image, draw = _canvas()
    user, year, totals = data["user"], data["year"], data["totals"]

    _text(draw, (70, 92), f"RETROSPECTIVA {year}", _font("ui-bold", _px(30)), ACCENT, "ls")
    if data["partial"]:
        label = _font("ui", _px(22))
        _text(draw, (70 + 6 + draw.textlength(f"RETROSPECTIVA {year}", font=_font("ui-bold", _px(30))) / _SCALE, 92), "  até agora", label, TEXT_3, "ls")
    font, shown = _fit(draw, _display(user["display_name"], user["username"]), "ui-bold", 58, 600, 30)  # termina antes do gráfico (x=700)
    _text(draw, (70, 160), shown, font, TEXT, "ls")

    # O número em destaque é o primeiro destes que existe (a página repete esta ordem no texto da imagem).
    number, caption = 0, "jogos zerados"
    for value, one, many in (
        (totals["completed"], "jogo zerado", "jogos zerados"),
        (totals["started"], "jogo começado", "jogos começados"),
        (data["ratings"]["count"], "nota dada", "notas dadas"),
        (totals["abandoned"], "jogo abandonado", "jogos abandonados"),
        (totals["replays"], "recomeço", "recomeços"),
    ):
        if value:
            number, caption = value, _plural(value, one, many)
            break
    number_font = _font("ui-bold", _px(190))
    _text(draw, (64, 360), str(number), number_font, ACCENT, "ls")
    shift = draw.textlength(str(number), font=number_font) / _SCALE
    _text(draw, (64 + shift + 22, 360), caption, _font("ui", _px(34)), TEXT, "ls")

    facts = []
    best = data["game_of_the_year"]
    if best and supported(best["game"]["name"]):
        facts.append(("Jogo do ano", best["game"]["name"]))
    if data["ratings"]["average"] is not None:
        count = data["ratings"]["count"]
        facts.append(("Nota média", f"{_pt_number(data['ratings']['average'])} em {count} {_plural(count, 'avaliação', 'avaliações')}"))
    for index, (label, value) in enumerate(facts[:2]):
        y = 436 + index * 74
        _text(draw, (70, y), label.upper(), _font("ui", _px(20)), TEXT_3, "ls")
        font, shown = _fit(draw, value, "read", 34, 520, 22)
        _text(draw, (70, y + 38), shown, font, TEXT, "ls")

    if totals["completed"]:
        _text(draw, (700, 130), "ZERADOS POR MÊS", _font("ui", _px(20)), TEXT_3, "ls")
        _month_bars(draw, data["by_month"], 700, 150, 430, 270)
    _brand(draw, 70 if not facts else 700, 540, size=40)
    return _finish(image)
