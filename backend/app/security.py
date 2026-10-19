"""Camadas de segurança HTTP: CSRF, verificação de origem, CORS, rate limit e cabeçalhos.

Autenticação por cookie de sessão exige proteção contra CSRF. Aqui isso é
feito em três camadas independentes:

1. Cookie SameSite=Lax (configurado em config.py) — o navegador não envia o
   cookie em POSTs disparados por outros sites.
2. Token de sessão: toda requisição que altera estado precisa enviar o cabeçalho
   X-CSRF-Token com o token guardado na sessão (padrão "synchronizer token").
3. Verificação do cabeçalho Origin, quando presente.
"""
from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import deque
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, Response, current_app, request, session

from .errors import ApiError

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CORS_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
CORS_HEADERS = "Content-Type, X-CSRF-Token"


# --------------------------------------------------------------------------- CSRF
def csrf_token() -> str:
    """Token de CSRF da sessão atual (criado na primeira chamada)."""
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def _check_origin() -> None:
    origin = request.headers.get("Origin")
    if origin is None:
        return
    allowed = origin in current_app.config["CORS_ORIGINS"]
    if not allowed and origin != "null":
        allowed = urlparse(origin).netloc == request.host
    if not allowed:
        raise ApiError(403, "origin_forbidden", "Origem da requisição não autorizada.")


def _check_csrf() -> None:
    expected = session.get("csrf")
    received = request.headers.get("X-CSRF-Token", "")
    if not expected or not received or not hmac.compare_digest(expected, received):
        raise ApiError(
            403,
            "csrf_invalid",
            "Sua sessão de segurança expirou. Recarregue a página e tente de novo.",
        )


# --------------------------------------------------------------------- Rate limit
_hits: dict[tuple[str, str], deque[float]] = {}
_hits_lock = threading.Lock()


def reset_rate_limits() -> None:
    with _hits_lock:
        _hits.clear()


def rate_limit(bucket: str, limit: int, per_seconds: int):
    """Limita `limit` chamadas a cada `per_seconds` por IP (janela deslizante).

    O contador fica na memória do processo: serve para instalações de um único
    processo (o caso do SQLite). Com vários processos o limite vale por processo.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if current_app.config.get("RATELIMIT_ENABLED", True):
                key = (bucket, request.remote_addr or "desconhecido")
                now = time.monotonic()
                with _hits_lock:
                    window = _hits.setdefault(key, deque())
                    while window and now - window[0] > per_seconds:
                        window.popleft()
                    if len(window) >= limit:
                        wait = int(per_seconds - (now - window[0])) + 1
                        raise ApiError(
                            429,
                            "rate_limited",
                            "Muitas tentativas em pouco tempo. Aguarde um instante e tente de novo.",
                            headers={"Retry-After": str(wait)},
                        )
                    window.append(now)
                    if len(_hits) > 5000:  # limpeza ocasional de IPs inativos
                        for stale in [k for k, v in _hits.items() if not v or now - v[-1] > per_seconds]:
                            _hits.pop(stale, None)
            return view(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- init
def init_security(app: Flask) -> None:
    @app.before_request
    def guard_api():
        if not request.path.startswith("/api/"):
            return None
        if request.method == "OPTIONS":  # pré-voo do CORS; os cabeçalhos entram no after_request
            return Response(status=204)
        if request.method in SAFE_METHODS:
            return None
        _check_origin()
        _check_csrf()
        return None

    @app.after_request
    def add_headers(response: Response):
        origin = request.headers.get("Origin")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers.add("Vary", "Origin")
            if origin and origin in current_app.config["CORS_ORIGINS"]:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                if request.method == "OPTIONS":
                    response.headers["Access-Control-Allow-Methods"] = CORS_METHODS
                    response.headers["Access-Control-Allow-Headers"] = CORS_HEADERS
                    response.headers["Access-Control-Max-Age"] = "600"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if current_app.config["IS_PRODUCTION"] and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
