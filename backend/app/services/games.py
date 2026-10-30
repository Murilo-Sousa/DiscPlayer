"""Cópia local mínima dos jogos referenciados por registros pessoais."""
from __future__ import annotations

from ..db import execute, fetch_one, transaction
from ..utils.dates import parse_iso_date, utcnow_iso
from . import rawg


def get_local_game(rawg_id: int) -> dict | None:
    row = fetch_one("SELECT * FROM games WHERE rawg_id = ?", (rawg_id,))
    return dict(row) if row else None


def release_of(detail: dict) -> str | None:
    """A data de lançamento da RAWG (AAAA-MM-DD) ou None: jogo sem data (ainda "a anunciar") ou data inválida."""
    released = detail.get("released")
    return released if parse_iso_date(released) else None


def _store(detail: dict) -> None:
    """Insere ou atualiza (nome, capa, data) a cópia local a partir da RAWG.

    A data de lançamento acompanha a RAWG, inclusive quando ela some (jogo adiado para "a anunciar"): uma data
    velha e futura guardada aqui continuaria a barrar quem quer jogar, enquanto a tela, que lê a RAWG, liberaria.
    """
    released = release_of(detail)
    with transaction():
        execute(
            """
            INSERT INTO games (rawg_id, name, slug, cover_url, release_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (rawg_id) DO UPDATE SET
                name = excluded.name,
                slug = excluded.slug,
                cover_url = COALESCE(excluded.cover_url, games.cover_url),
                release_date = excluded.release_date
            """,
            (
                detail["rawg_id"],
                detail["name"][:200],
                detail["slug"][:200],
                detail.get("cover_url"),
                released,
                utcnow_iso(),
            ),
        )


def ensure_game(rawg_id: int) -> dict:
    """Devolve o jogo local, buscando na RAWG se ainda não existir.

    Os metadados vêm sempre do servidor (nunca do cliente), para que ninguém
    cadastre um jogo com nome ou capa falsos. Deve ser chamada ANTES de abrir
    uma transação de escrita, já que faz uma requisição de rede.
    """
    local = get_local_game(rawg_id)
    if local:
        return local
    _store(rawg.get_game(rawg_id))  # pode levantar RawgError
    return get_local_game(rawg_id)  # type: ignore[return-value]


def sync_game(detail: dict) -> dict:
    """Atualiza a cópia local com dados frescos da RAWG (chamada na página do jogo)."""
    _store(detail)
    return get_local_game(detail["rawg_id"])  # type: ignore[return-value]
