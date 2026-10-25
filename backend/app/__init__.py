"""DiscPlayer — back-end Flask (API REST + SQLite)."""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db as database
from .config import build_config
from .errors import register_error_handlers
from .security import init_security


def _resolve_secret_key(app: Flask) -> None:
    key = app.config.get("SECRET_KEY")
    if app.config["IS_PRODUCTION"]:
        if not key or len(key) < 32:
            raise RuntimeError(
                "Em produção, defina SECRET_KEY com pelo menos 32 caracteres. "
                'Gere uma com: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return
    if key:
        return
    if app.config.get("TESTING"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        return
    # Desenvolvimento: uma chave aleatória guardada fora do código, para que as
    # sessões sobrevivam a reinicializações do servidor.
    key_file = Path(app.instance_path) / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    app.config["SECRET_KEY"] = key_file.read_text(encoding="utf-8").strip()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True, static_folder=None)
    app.config.update(build_config())
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    _resolve_secret_key(app)
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = str(Path(app.instance_path) / "discplayer.db")

    app.json.ensure_ascii = False  # acentos legíveis no JSON
    app.json.sort_keys = False

    proxies = app.config["TRUSTED_PROXY_COUNT"]
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)  # type: ignore[method-assign]

    if not app.config.get("TESTING"):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database.init_app(app)
    register_error_handlers(app)
    init_security(app)
    _register_blueprints(app)

    if app.config["AUTO_MIGRATE"]:
        with app.app_context():
            database.migrate()
    return app


def _register_blueprints(app: Flask) -> None:
    from .routes import auth, avatars, feed, games, health, library, lists, reviews, search, share, spa, users

    for module in (health, auth, avatars, games, library, reviews, lists, users, feed, search, share):
        app.register_blueprint(module.bp)
    app.register_blueprint(spa.bp)  # por último: captura o que não for /api
