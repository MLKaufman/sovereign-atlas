"""Database initialization, migrations, and data access helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path

import duckdb

DEFAULT_DB = Path("data/markercodex.duckdb")
MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


def connect(path: str | Path = DEFAULT_DB, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def initialize(path: str | Path = DEFAULT_DB) -> None:
    """Create a database and apply every pending numbered SQL migration."""
    with connect(path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY, name VARCHAR NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )"""
        )
        applied = {
            row[0] for row in con.execute("SELECT version FROM schema_migrations").fetchall()
        }
        migration_dir = files("markercodex").joinpath("migrations")
        migrations = []
        for item in migration_dir.iterdir():
            match = MIGRATION_RE.match(item.name)
            if match:
                migrations.append((int(match.group(1)), item))
        for version, item in sorted(migrations):
            if version in applied:
                continue
            sql = item.read_text(encoding="utf-8")
            con.begin()
            try:
                con.execute(sql)
                con.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    [version, item.name],
                )
                con.commit()
            except Exception:
                con.rollback()
                raise


@contextmanager
def database(
    path: str | Path = DEFAULT_DB, *, read_only: bool = False
) -> Iterator[duckdb.DuckDBPyConnection]:
    con = connect(path, read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
        ).fetchone()[0]
    )
