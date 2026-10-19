"""Erros da API: formato único de resposta e tradução de exceções."""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Erro previsto: vira uma resposta JSON com status e código estáveis."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields
        self.headers = headers or {}


def error_response(
    status: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
):
    body: dict = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    response = jsonify(body)
    response.status_code = status
    for name, value in (headers or {}).items():
        response.headers[name] = value
    return response


_HTTP_MESSAGES = {
    400: ("bad_request", "Requisição inválida."),
    401: ("auth_required", "Entre na sua conta para continuar."),
    403: ("forbidden", "Você não tem permissão para fazer isso."),
    404: ("not_found", "Recurso não encontrado."),
    405: ("method_not_allowed", "Método não permitido para este endereço."),
    413: ("payload_too_large", "O conteúdo enviado é grande demais."),
    415: ("unsupported_media_type", "Envie o corpo da requisição como JSON."),
    429: ("rate_limited", "Muitas requisições. Tente novamente em instantes."),
}


def register_error_handlers(app: Flask) -> None:
    # Importado aqui para evitar import circular (a RAWG usa utilitários do app).
    from .services.rawg import RawgError

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_response(error.status, error.code, error.message, error.fields, error.headers)

    @app.errorhandler(RawgError)
    def handle_rawg_error(error: RawgError):
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
        return error_response(error.status, error.code, error.message, headers=headers)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        status = error.code or 500
        code, message = _HTTP_MESSAGES.get(status, ("http_error", error.name))
        return error_response(status, code, message)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        # O stack trace vai só para o log do servidor, nunca para a resposta.
        logger.exception("Erro inesperado: %s", type(error).__name__)
        return error_response(500, "internal_error", "Algo deu errado do nosso lado. Tente novamente.")
