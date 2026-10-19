"""Acesso ao SQLite: conexão por requisição, transações e migrações em SQL.

Cada conexão ativa as chaves estrangeiras (o SQLite as desativa por padrão),
usa WAL para que leituras não bloqueiem a escrita e espera até 15 s por locks
antes de falhar. As escritas usam BEGIN IMMEDIATE: o SQLite aceita um escritor
por vez, então pegar o lock logo no início evita deadlocks por promoção de
transação.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import click
from flask import Flask, current_app, g

from .utils.dates import utcnow_iso

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect(path: str | Path) -> sqlite3.Connection:
    # isolation_level=None: o módulo não abre transações por conta própria;
    # quem controla BEGIN/COMMIT é `transaction()`.
    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
        g.tx_depth = 0
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction():
    """Bloco atômico. Reentrante: blocos aninhados participam do externo."""
    conn = get_db()
    if g.tx_depth > 0:
        g.tx_depth += 1
        try:
            yield conn
        finally:
            g.tx_depth -= 1
        return
    conn.execute("BEGIN IMMEDIATE")
    g.tx_depth = 1
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
    finally:
        g.tx_depth = 0


def fetch_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def fetch_all(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def execute(sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
    return get_db().execute(sql, params)


def _statements(script: str):
    """Divide um script SQL em instruções completas (respeitando triggers)."""
    buffer = ""
    for line in script.splitlines(keepends=True):
        stripped = line.strip()
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer.strip()
            buffer = ""
    if buffer.strip():
        yield buffer.strip()


def migrate(path: str | Path | None = None) -> list[str]:
    """Aplica as migrações pendentes (migrations/NNNN_nome.sql), em ordem.

    Cada arquivo roda em uma transação própria, junto com o registro em
    `schema_migrations`; se algo falhar, nada daquele arquivo fica aplicado.
    Retorna os nomes das migrações aplicadas nesta chamada.
    """
    conn = connect(path or current_app.config["DATABASE"])
    applied_now: list[str] = []
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.execute("BEGIN IMMEDIATE")
            try:
                done = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (file.stem,)
                ).fetchone()
                if done:
                    conn.execute("ROLLBACK")
                    continue
                for statement in _statements(file.read_text(encoding="utf-8")):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (file.stem, utcnow_iso()),
                )
                conn.execute("COMMIT")
                applied_now.append(file.stem)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
    finally:
        conn.close()
    return applied_now


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Cria o banco e aplica as migrações pendentes."""
        applied = migrate()
        if applied:
            click.echo("Migrações aplicadas: " + ", ".join(applied))
        else:
            click.echo("Banco já está atualizado.")
