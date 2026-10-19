"""Servidor HTTP que imita a RAWG (dados fictícios!) para desenvolver sem chave.

    python -m tests.fake_rawg_server            # porta 8765
    RAWG_BASE_URL=http://127.0.0.1:8765/api RAWG_API_KEY=qualquer-coisa flask --app wsgi run

Ele valida que a chave (`?key=`) foi enviada, como a RAWG de verdade, e responde
com os mesmos formatos. Os jogos e as imagens NÃO são reais: use só em desenvolvimento.
"""
from __future__ import annotations

import argparse

from flask import Flask, jsonify, request

from app.services.rawg import RawgError
from tests import fake_rawg


def create_fake_server() -> Flask:
    app = Flask(__name__)

    @app.get("/api/<path:path>")
    def proxy(path: str):
        if not request.args.get("key"):
            return jsonify({"detail": "Authentication credentials were not provided."}), 401
        params = {k: v for k, v in request.args.items() if k != "key"}
        try:
            return jsonify(fake_rawg.fetch_json(path, params))
        except RawgError as exc:
            return jsonify({"detail": exc.message}), exc.status

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    create_fake_server().run(host="127.0.0.1", port=args.port)
