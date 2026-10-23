"""Exclusão de conta."""
from __future__ import annotations

from ..db import execute, transaction


def delete_account(user_id: int) -> None:
    """Apaga a conta e tudo que é dela, em uma única transação.

    As chaves estrangeiras (todas com ON DELETE CASCADE) levam junto: diário e jogadas
    anteriores, reviews (e as curtidas que elas receberam), curtidas dadas a outras
    reviews, listas e seus jogos, quem a pessoa segue e quem a segue, o histórico de
    atividades e a foto. O que pertence a outras pessoas não é tocado, e o catálogo de
    jogos (`games`) é compartilhado e permanece.
    """
    with transaction():
        execute("DELETE FROM users WHERE id = ?", (user_id,))
