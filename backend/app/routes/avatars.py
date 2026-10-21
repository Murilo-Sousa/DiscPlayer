"""Entrega das fotos de perfil enviadas pelas pessoas."""
from __future__ import annotations

from flask import Blueprint, Response

from ..errors import ApiError
from ..services import avatars as avatars_service

bp = Blueprint("avatars", __name__, url_prefix="/api/avatars")


@bp.get("/<token>")
def avatar(token: str):
    """A imagem de um token. O token muda a cada troca de foto, então o cache pode ser eterno."""
    row = avatars_service.get_by_token(token)
    if row is None:
        raise ApiError(404, "not_found", "Foto não encontrada.")
    response = Response(row["data"], mimetype="image/webp")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # Mesmo abrindo o endereço da foto direto no navegador, nada executa.
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
