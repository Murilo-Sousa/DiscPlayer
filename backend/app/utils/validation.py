"""Validação de entrada no servidor.

O React também valida, mas nada aqui confia nele: cada regra do front-end
existe de novo neste módulo.
"""
from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

from flask import request

from ..errors import ApiError
from .dates import max_allowed_date, parse_iso_date

UNSET: Any = object()  # "campo ausente" (diferente de null, que limpa o campo)

# Controles invisíveis e de direção de texto (usados para disfarçar conteúdo).
_BIDI = "‪‫‬‭‮⁦⁧⁨⁩"
_CONTROL_SINGLE = re.compile("[\x00-\x1f\x7f" + _BIDI + "]")
_CONTROL_MULTI = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f" + _BIDI + "]")

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
RESERVED_USERNAMES = {
    "admin", "administrador", "discplayer", "suporte", "support", "root", "api",
    "moderador", "sistema", "system", "null", "undefined", "anonimo",
}
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1", "senha123",
    "qwertyui", "qwerty123", "11111111", "abcd1234", "iloveyou", "senhasenha",
}


class FieldErrors:
    """Acumula erros por campo e os levanta de uma vez como HTTP 422."""

    def __init__(self) -> None:
        self.fields: dict[str, str] = {}

    def add(self, name: str, message: str) -> None:
        self.fields.setdefault(name, message)

    def __bool__(self) -> bool:
        return bool(self.fields)

    def raise_if_any(self) -> None:
        if self.fields:
            raise ApiError(422, "validation_error", "Revise os campos destacados.", fields=dict(self.fields))


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Envie os dados como um objeto JSON.")
    return data


def clean_text(value: str, multiline: bool = False) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if multiline:
        value = _CONTROL_MULTI.sub("", value)
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
    else:
        value = _CONTROL_SINGLE.sub(" ", value)
        value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_text(
    data: dict,
    key: str,
    label: str,
    errors: FieldErrors,
    *,
    required: bool = False,
    min_len: int = 0,
    max_len: int = 1000,
    multiline: bool = False,
) -> Any:
    """Texto limpo; None se vazio/nulo; UNSET se o campo não veio."""
    if key not in data:
        if required:
            errors.add(key, f"{label} é obrigatório.")
        return UNSET
    value = data[key]
    if value is None:
        if required:
            errors.add(key, f"{label} é obrigatório.")
        return None
    if not isinstance(value, str):
        errors.add(key, f"{label} deve ser um texto.")
        return UNSET
    text = clean_text(value, multiline=multiline)
    if not text:
        if required or min_len > 0:
            errors.add(key, f"{label} é obrigatório.")
            return UNSET
        return None
    if len(text) < min_len:
        errors.add(key, f"{label} deve ter pelo menos {min_len} caracteres.")
        return UNSET
    if len(text) > max_len:
        errors.add(key, f"{label} deve ter no máximo {max_len} caracteres.")
        return UNSET
    return text


def parse_rating(value: Any) -> float:
    """Nota de 0 a 10 em passos de 0,5. Levanta ValueError se inválida."""
    if isinstance(value, bool):
        raise ValueError("bool")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        number = float(value.strip().replace(",", "."))
    else:
        raise ValueError("tipo")
    if not math.isfinite(number) or number < 0 or number > 10 or (number * 2) != int(number * 2):
        raise ValueError("escala")
    return number


def read_rating(data: dict, errors: FieldErrors, *, required: bool = False, key: str = "rating") -> Any:
    if key not in data or data[key] is None:
        if required:
            errors.add(key, "Informe uma nota de 0 a 10.")
        return UNSET
    try:
        return parse_rating(data[key])
    except (ValueError, TypeError):
        errors.add(key, "A nota deve ficar entre 0 e 10, em passos de 0,5.")
        return UNSET


def read_bool(data: dict, key: str, label: str, errors: FieldErrors) -> Any:
    if key not in data:
        return UNSET
    if not isinstance(data[key], bool):
        errors.add(key, f"{label} deve ser verdadeiro ou falso.")
        return UNSET
    return data[key]


def read_date(data: dict, key: str, label: str, errors: FieldErrors) -> Any:
    """'AAAA-MM-DD' (str), None (limpar) ou UNSET (ausente)."""
    if key not in data:
        return UNSET
    value = data[key]
    if value is None or value == "":
        return None
    parsed = parse_iso_date(value)
    if parsed is None:
        errors.add(key, f"{label} deve estar no formato AAAA-MM-DD.")
        return UNSET
    if parsed > max_allowed_date():
        errors.add(key, f"{label} não pode estar no futuro.")
        return UNSET
    if parsed.year < 1970:
        errors.add(key, f"{label} é anterior a 1970.")
        return UNSET
    return parsed.isoformat()


def read_url(
    data: dict,
    key: str,
    label: str,
    errors: FieldErrors,
    *,
    max_len: int = 500,
    schemes: tuple[str, ...] = ("http", "https"),
) -> Any:
    """URL válida (só os esquemas permitidos), None (limpar) ou UNSET. Barra javascript:, data: etc."""
    if key not in data:
        return UNSET
    value = data[key]
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        errors.add(key, f"{label} deve ser um endereço web.")
        return UNSET
    value = value.strip()
    parsed = urlparse(value)
    if (
        len(value) > max_len
        or re.search(r"\s", value)
        or parsed.scheme not in schemes
        or not parsed.netloc
    ):
        shown = "https" if schemes == ("https",) else "http(s)"
        errors.add(key, f"{label} deve ser um endereço {shown} válido de até {max_len} caracteres.")
        return UNSET
    return value


def read_username(data: dict, errors: FieldErrors) -> Any:
    raw = data.get("username")
    if not isinstance(raw, str) or not raw.strip():
        errors.add("username", "Escolha um nome de usuário.")
        return UNSET
    value = raw.strip().lower()
    if not USERNAME_RE.match(value):
        errors.add("username", "Use de 3 a 24 caracteres: letras minúsculas, números e _.")
        return UNSET
    if value in RESERVED_USERNAMES:
        errors.add("username", "Esse nome de usuário não está disponível.")
        return UNSET
    return value


def read_email(data: dict, errors: FieldErrors) -> Any:
    raw = data.get("email")
    if not isinstance(raw, str) or not raw.strip():
        errors.add("email", "Informe seu e-mail.")
        return UNSET
    value = raw.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        errors.add("email", "Informe um e-mail válido.")
        return UNSET
    return value


def read_password(data: dict, errors: FieldErrors, *, username: str | None = None, email: str | None = None) -> Any:
    raw = data.get("password")
    if not isinstance(raw, str) or not raw:
        errors.add("password", "Escolha uma senha.")
        return UNSET
    if len(raw) < 8:
        errors.add("password", "A senha deve ter pelo menos 8 caracteres.")
        return UNSET
    if len(raw) > 128:
        errors.add("password", "A senha deve ter no máximo 128 caracteres.")
        return UNSET
    lowered = raw.lower()
    if lowered in COMMON_PASSWORDS or lowered in {(username or "").lower(), (email or "").lower()}:
        errors.add("password", "Essa senha é fácil demais de adivinhar. Escolha outra.")
        return UNSET
    return raw
