from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..db import fetch_one

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    fetch_one("SELECT 1")  # falha (500) se o banco não estiver acessível
    return jsonify(
        {
            "status": "ok",
            "database": "ok",
            # Apenas informa se a chave existe — nunca o valor dela.
            "rawg_configured": bool(current_app.config["RAWG_API_KEY"]),
        }
    )
