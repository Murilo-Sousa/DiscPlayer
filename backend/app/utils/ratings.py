"""A distribuição de notas, igual no perfil, na retrospectiva e na página do jogo.

As notas vão de 0 a 10 em passos de 0,5, então o gráfico tem 11 barras (0 a 10): a barra n reúne a nota n e a
nota n + 0,5 (de 0 a 9), e a barra 10 é só a nota 10. O banco só aceita notas nesse intervalo (CHECK da
tabela `reviews`), então o índice nunca sai da lista.
"""
from __future__ import annotations

from typing import Iterable

RATING_BARS = 11


def empty_distribution() -> list[int]:
    return [0] * RATING_BARS


def distribution_from(rows: Iterable) -> list[int]:
    """Monta a lista de contagens a partir de linhas `bucket` (parte inteira da nota) e `n` (quantas)."""
    bars = empty_distribution()
    for row in rows:
        bars[row["bucket"]] = row["n"]
    return bars
