"""Servidor HTTP que imita o IGDB e o login da Twitch (dados fictícios!) para desenvolver sem credenciais.

    python -m tests.fake_igdb_server            # porta 8765
    IGDB_BASE_URL=http://127.0.0.1:8765/v4 IGDB_TOKEN_URL=http://127.0.0.1:8765/oauth2/token \\
    IGDB_CLIENT_ID=qualquer IGDB_CLIENT_SECRET=qualquer flask --app wsgi run

Ele exige o Client-ID e o token (como o IGDB de verdade), entende o texto Apicalypse que o back-end envia e responde
com os mesmos formatos. Os jogos e as imagens NÃO são reais: use só em desenvolvimento.
"""
from __future__ import annotations

import argparse
import re

from flask import Flask, jsonify, request

from app.services.igdb import IgdbError, Query
from tests import fake_igdb

TOKEN = "token-de-mentira"

_NUMBER = r"-?\d+"
_CLAUSE = re.compile(
    rf"^(?P<field>[a-z_][a-z0-9_.]*) (?P<op>=|!=|>=|<=|>|<) (?P<value>null|\([\d,\s-]+\)|{_NUMBER})$"
)


def parse_apicalypse(endpoint: str, body: str) -> Query:
    """O inverso de `igdb.to_apicalypse`, para o que o back-end sabe escrever."""
    count = endpoint.endswith("/count")
    fields: tuple[str, ...] = ()
    filters: list[tuple] = []
    search = sort = None
    limit, offset = 10, 0
    for statement in (s.strip() for s in body.split(";") if s.strip()):
        keyword, _, rest = statement.partition(" ")
        rest = rest.strip()
        if keyword == "fields":
            fields = tuple(f.strip() for f in rest.split(","))
        elif keyword == "where":
            for text in rest.split(" & "):
                match = _CLAUSE.match(text.strip())
                if not match:
                    raise ValueError(f"filtro desconhecido: {text!r}")
                field, op, value = match["field"], match["op"], match["value"]
                if value == "null":
                    filters.append((field, "null" if op == "=" else "notnull", None))
                elif value.startswith("("):
                    filters.append((field, "in", tuple(int(v) for v in value.strip("()").split(","))))
                else:
                    filters.append((field, op, int(value)))
        elif keyword == "search":
            search = rest.strip('"')
        elif keyword == "sort":
            sort = rest
        elif keyword == "limit":
            limit = int(rest)
        elif keyword == "offset":
            offset = int(rest)
        else:
            raise ValueError(f"comando desconhecido: {keyword!r}")
    return Query(endpoint.removesuffix("/count"), fields, tuple(filters), search, sort, limit, offset, count)


def create_fake_server() -> Flask:
    app = Flask(__name__)

    @app.post("/oauth2/token")
    def token():
        if not request.form.get("client_id") or not request.form.get("client_secret"):
            return jsonify({"status": 400, "message": "invalid client"}), 400
        return jsonify({"access_token": TOKEN, "expires_in": 5_000_000, "token_type": "bearer"})

    @app.post("/v4/<path:path>")
    def proxy(path: str):
        if not request.headers.get("Client-ID") or request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return jsonify({"message": "Authorization Failure."}), 401
        try:
            query = parse_apicalypse(path, request.get_data(as_text=True))
            return jsonify(fake_igdb.fetch_json(query))
        except ValueError as exc:
            return jsonify([{"title": "Syntax Error", "status": 400, "cause": str(exc)}]), 400
        except IgdbError as exc:
            return jsonify({"message": exc.message}), exc.status

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    create_fake_server().run(host="127.0.0.1", port=args.port)
