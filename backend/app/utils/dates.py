from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """Instante atual em UTC no formato usado por todas as colunas *_at."""
    return utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc() -> date:
    return utcnow().date()


def parse_iso_date(value: object) -> date | None:
    """Converte 'AAAA-MM-DD' em date. Retorna None se o formato for inválido."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def max_allowed_date() -> date:
    """Limite para datas informadas pelo usuário.

    Permite um dia à frente de UTC para não rejeitar quem está em fusos
    adiantados (por exemplo, no fim da tarde na Nova Zelândia).
    """
    return today_utc() + timedelta(days=1)
