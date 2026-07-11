#!/usr/bin/env python3
"""
Inicializa PostgreSQL en Render: solo esquema (tablas vacías), sin datos de negocio.

Flujo:
  1. migrate hasta core.0001
  2. bootstrap SQL: empresa, sucursal, cliente, proveedor
  3. migrate resto de apps
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_SQL = ROOT / "docs/sql/00_bootstrap_core_tablas_postgresql.sql"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_database_url(url: str | None) -> str:
    raw = (url or os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        print("ERROR: Defina DATABASE_URL (External Database URL de Render).", file=sys.stderr)
        sys.exit(1)
    if "sslmode=" not in raw and "render.com" in raw:
        sep = "&" if "?" in raw else "?"
        raw = f"{raw}{sep}sslmode=require"
    os.environ["DATABASE_URL"] = raw
    return raw


def _python_exe() -> str:
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _run_manage(*args: str) -> None:
    cmd = [_python_exe(), str(ROOT / "manage.py"), *args]
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def _django_setup() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _db_schema() -> str:
    _django_setup()
    from django.conf import settings

    return (getattr(settings, "DB_SCHEMA", "public") or "public").strip()


def _ensure_db_schema() -> None:
    schema = _db_schema()
    if schema == "public":
        return
    _django_setup()
    from django.db import connection

    print(f"\n>> Asegurando esquema PostgreSQL: {schema}")
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def _table_exists(table: str) -> bool:
    _django_setup()
    from django.db import connection

    schema = _db_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
            """,
            [schema, table],
        )
        return bool(cursor.fetchone()[0])


def _sql_statements(sql: str) -> list[str]:
    begin = sql.find("BEGIN;")
    if begin == -1:
        return []
    block = sql[begin:].replace("BEGIN;", "").replace("COMMIT;", "")
    statements: list[str] = []
    for part in block.split(";"):
        stmt = "\n".join(
            line for line in part.splitlines() if line.strip() and not line.strip().startswith("--")
        ).strip()
        if stmt:
            statements.append(stmt)
    return statements


def _run_bootstrap_sql() -> None:
    if not BOOTSTRAP_SQL.is_file():
        print(f"ERROR: No se encontró {BOOTSTRAP_SQL}", file=sys.stderr)
        sys.exit(1)
    if _table_exists("empresa"):
        print("\n>> Bootstrap omitido: la tabla 'empresa' ya existe.")
        return

    statements = _sql_statements(BOOTSTRAP_SQL.read_text(encoding="utf-8"))
    _django_setup()
    from django.db import connection

    print(f"\n>> Ejecutando bootstrap ({len(statements)} sentencias)")
    with connection.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)
    print(">> Bootstrap aplicado.")


def _count_tables() -> int:
    _django_setup()
    from django.db import connection

    schema = _db_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            """,
            [schema],
        )
        return int(cursor.fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea esquema PostgreSQL en Render.")
    parser.add_argument("--create-owner", action="store_true")
    parser.add_argument("--skip-bootstrap", action="store_true")
    args = parser.parse_args()

    db_url = _ensure_database_url(None)
    host_hint = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "(oculto)"
    print(f"Destino: {host_hint}")

    _ensure_db_schema()
    _run_manage("migrate", "core", "0001", "--noinput")
    if not args.skip_bootstrap:
        _run_bootstrap_sql()
    _run_manage("migrate", "--noinput")

    print(f"\nListo. Tablas en {_db_schema()}: {_count_tables()}")

    if args.create_owner:
        _run_manage("ensure_platform_owner")


if __name__ == "__main__":
    main()
