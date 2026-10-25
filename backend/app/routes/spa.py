"""Entrega do front-end compilado (npm run build) em produção.

Em desenvolvimento o React roda no servidor do Vite (porta 5173) e este módulo
não é usado: sem a pasta `frontend/dist`, as rotas abaixo respondem com uma
orientação em vez de uma página quebrada.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from flask import Blueprint, Response, current_app, request, send_from_directory

from ..security import check_rate
from ..services import previews

bp = Blueprint("spa", __name__)

# O front-end só carrega recursos do próprio domínio, com duas exceções:
# imagens (capas da RAWG em https; a foto de perfil é do próprio domínio; blob: é a prévia da foto
# escolhida, criada pelo próprio navegador antes do envio) e estilos em linha do React (atributo style).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https: data: blob:; font-src 'self'; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)

_MISSING = (
    "O front-end ainda não foi compilado.\n"
    "Em desenvolvimento, abra http://localhost:5173 (npm run dev dentro de frontend/).\n"
    "Para servir tudo por aqui, rode npm run build dentro de frontend/.\n"
)


def _dist() -> Path:
    return Path(current_app.config["FRONTEND_DIST"])


# --------------------------------------------------------------------------- prévia de links
# Pedidos por minuto e por IP que consultam o banco para montar a prévia. Folgado de propósito: os robôs de
# prévia (WhatsApp, Discord...) saem de poucos IPs e um link muito compartilhado gera rajadas. Passou do limite,
# a página abre normalmente com a prévia padrão.
PREVIEW_LIMIT = 600

_TITLE = re.compile(r"<title>.*?</title>", re.S | re.I)
_DESCRIPTION = re.compile(r"""<meta\s+name=["']description["'][^>]*>""", re.S | re.I)
_index_cache: dict[str, tuple[int, str]] = {}


def _index_html(dist: Path) -> str:
    """O index.html compilado, relido só quando o arquivo muda."""
    path = dist / "index.html"
    stamp = path.stat().st_mtime_ns
    cached = _index_cache.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]
    text = path.read_text(encoding="utf-8")
    _index_cache[str(path)] = (stamp, text)
    return text


def _site_base() -> str:
    """Endereço do site nos links absolutos (as prévias exigem URL completa): PUBLIC_URL ou o da requisição."""
    return current_app.config.get("PUBLIC_URL") or request.url_root.rstrip("/")


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _head_block(preview: previews.Preview, url: str) -> str:
    def meta(attr: str, name: str, content: str) -> str:
        return f'<meta {attr}="{name}" content="{_esc(content)}" />'

    lines = [
        f"<title>{_esc(preview.title)}</title>",
        meta("name", "description", preview.description),
        f'<link rel="canonical" href="{_esc(url)}" />',
        meta("property", "og:site_name", previews.SITE_NAME),
        meta("property", "og:type", "website"),
        meta("property", "og:locale", "pt_BR"),
        meta("property", "og:title", preview.title),
        meta("property", "og:description", preview.description),
        meta("property", "og:url", url),
    ]
    if preview.image:
        lines.append(meta("property", "og:image", preview.image))
        if preview.image_alt:
            lines.append(meta("property", "og:image:alt", preview.image_alt))
        if preview.image_size:
            lines.append(meta("property", "og:image:width", str(preview.image_size[0])))
            lines.append(meta("property", "og:image:height", str(preview.image_size[1])))
        lines.append(meta("name", "twitter:card", preview.card))
        lines.append(meta("name", "twitter:image", preview.image))
        if preview.image_alt:
            lines.append(meta("name", "twitter:image:alt", preview.image_alt))
    else:
        lines.append(meta("name", "twitter:card", "summary"))
    lines.append(meta("name", "twitter:title", preview.title))
    lines.append(meta("name", "twitter:description", preview.description))
    return "\n    ".join(lines)


def render_index(dist: Path, path: str) -> str:
    """O index.html com título, descrição e imagem de prévia do endereço pedido."""
    base = _site_base()
    if previews.is_dynamic(path) and check_rate("preview", PREVIEW_LIMIT, 60) is not None:
        preview = previews.default_preview(base)  # excesso de pedidos: não gasta banco nem RAWG
    else:
        preview = previews.for_path(path, base)
    url = f"{base}/{path.strip('/')}"
    text = _index_html(dist)
    text = _TITLE.sub("", text, count=1)
    text = _DESCRIPTION.sub("", text, count=1)
    block = _head_block(preview, url)
    if "</head>" in text:
        return text.replace("</head>", f"    {block}\n  </head>", 1)
    return block + text


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
def frontend(path: str):
    dist = _dist()
    if path.startswith("api/"):  # endereço de API inexistente: nunca devolver HTML
        from werkzeug.exceptions import NotFound

        raise NotFound()
    if not (dist / "index.html").is_file():
        return Response(_MISSING, status=404, mimetype="text/plain")

    candidate = (dist / path).resolve()
    if path and candidate.is_file() and dist.resolve() in candidate.parents:
        response = send_from_directory(dist, path)
        if path.startswith("assets/"):  # arquivos com hash no nome: cache longo
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # Qualquer outro caminho é uma rota do React: devolve o index.html, já com a prévia de links dela.
    response = Response(render_index(dist, path), mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response
