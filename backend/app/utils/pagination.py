from __future__ import annotations

from flask import request

from ..errors import ApiError


def _int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"O parâmetro '{name}' deve ser um número inteiro.")
    if not minimum <= value <= maximum:
        raise ApiError(
            400, "invalid_parameter", f"O parâmetro '{name}' deve estar entre {minimum} e {maximum}."
        )
    return value


def page_args(default_per_page: int = 20, max_per_page: int = 50) -> tuple[int, int]:
    """Lê ?page= e ?per_page= validando os limites."""
    page = _int_arg("page", 1, 1, 10_000)
    per_page = _int_arg("per_page", default_per_page, 1, max_per_page)
    return page, per_page


def paginate_sql(page: int, per_page: int) -> tuple[str, tuple[int, int]]:
    """Trecho LIMIT/OFFSET. Busca uma linha a mais para saber se há próxima página."""
    return " LIMIT ? OFFSET ?", (per_page + 1, (page - 1) * per_page)


def page_envelope(rows: list, page: int, per_page: int, items: list | None = None) -> dict:
    """Monta {items, page, per_page, has_next} a partir de linhas buscadas com +1."""
    visible = rows[:per_page]
    return {
        "items": items if items is not None else visible,
        "page": page,
        "per_page": per_page,
        "has_next": len(rows) > per_page,
    }
