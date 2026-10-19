from __future__ import annotations

import re
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_html(value: str | None, max_len: int = 6000) -> str:
    """Converte HTML em texto puro (parágrafos separados por linha em branco).

    A descrição dos jogos vem da RAWG como HTML. Em vez de tentar "sanitizar"
    HTML, o back-end entrega apenas texto e o React o renderiza como texto, o
    que elimina a superfície de XSS.
    """
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\r", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:max_len]


def escape_like(term: str) -> str:
    """Escapa %, _ e \\ para uso em LIKE ... ESCAPE '\\'."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
