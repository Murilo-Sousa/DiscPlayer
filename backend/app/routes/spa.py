"""Entrega do front-end compilado (npm run build) em produção.

Em desenvolvimento o React roda no servidor do Vite (porta 5173) e este módulo
não é usado: sem a pasta `frontend/dist`, as rotas abaixo respondem com uma
orientação em vez de uma página quebrada.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, send_from_directory

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

    # Qualquer outro caminho é uma rota do React: devolve o index.html.
    response = send_from_directory(dist, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response
