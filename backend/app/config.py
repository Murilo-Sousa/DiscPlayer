"""Configuração lida do ambiente (e do arquivo .env) a cada create_app()."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except ValueError:
        return default


def _list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def build_config() -> dict:
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    is_production = app_env == "production"
    return {
        "APP_ENV": app_env,
        "IS_PRODUCTION": is_production,
        # Em produção a chave é obrigatória; em desenvolvimento ela é gerada e
        # guardada em instance/secret_key (veja app/__init__.py).
        "SECRET_KEY": os.environ.get("SECRET_KEY", "").strip() or None,
        "DATABASE": os.environ.get("DATABASE_PATH", "").strip() or None,
        "AUTO_MIGRATE": _bool("AUTO_MIGRATE", True),
        # Sessão e cookies
        "SESSION_COOKIE_NAME": "discplayer_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        # Em produção o cookie só trafega por HTTPS. Se for testar o build de
        # produção em http://localhost, defina COOKIE_SECURE=false.
        "SESSION_COOKIE_SECURE": _bool("COOKIE_SECURE", is_production),
        "PERMANENT_SESSION_LIFETIME": timedelta(days=30),
        "PASSWORD_HASH_METHOD": "scrypt",
        # Os corpos JSON são pequenos; 64 KB cobre uma review de 5.000 caracteres
        # com folga e barra uploads indevidos.
        "MAX_CONTENT_LENGTH": 64 * 1024,
        # Exceção: o envio da foto do perfil (multipart) aceita arquivos maiores, só nessa rota.
        "AVATAR_MAX_UPLOAD_BYTES": 5 * 1024 * 1024,
        # CORS / proxy
        "CORS_ORIGINS": _list(
            "CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
        ),
        "TRUSTED_PROXY_COUNT": _int("TRUSTED_PROXY_COUNT", 0),
        "RATELIMIT_ENABLED": _bool("RATELIMIT_ENABLED", True),
        # RAWG
        "RAWG_API_KEY": os.environ.get("RAWG_API_KEY", "").strip(),
        "RAWG_BASE_URL": os.environ.get("RAWG_BASE_URL", "https://api.rawg.io/api").strip().rstrip("/"),
        "RAWG_TIMEOUT": (3.05, 8.0),  # (conexão, leitura) em segundos
        "RAWG_TTL_SEARCH": 300,
        "RAWG_TTL_FEATURED": 1800,
        "RAWG_TTL_DETAIL": 6 * 3600,
        "RAWG_TTL_LOOKUPS": 24 * 3600,
        # Quanto tempo um item expirado ainda pode ser servido se a RAWG falhar.
        "RAWG_STALE_TTL": 7 * 24 * 3600,
        # Front-end compilado (npm run build) servido pelo Flask em produção.
        "FRONTEND_DIST": str(PROJECT_DIR / "frontend" / "dist"),
    }
