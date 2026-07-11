#!/usr/bin/env python3
"""
Copia PostgreSQL local → Render (esquema gestorVentas).

Requisitos: pg_dump y pg_restore (PostgreSQL client tools).

Uso:
  copy .env.render.example .env.render   # DATABASE_URL = External URL de Render
  python scripts/sync_local_to_render.py --yes

Variables:
  LOCAL_DATABASE_URL  — origen (default: DATABASE_URL de .env con localhost)
  DATABASE_URL        — destino Render (.env.render o entorno)
  DB_SCHEMA           — esquema a copiar (default: gestorVentas)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
BACKUPS = ROOT / "backups"


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _pick_local_url(env: dict[str, str]) -> str:
    explicit = (env.get("LOCAL_DATABASE_URL") or os.environ.get("LOCAL_DATABASE_URL") or "").strip()
    if explicit:
        return explicit
    candidates = [v.strip() for k, v in env.items() if k == "DATABASE_URL" and v.strip()]
    for url in reversed(candidates):
        if "localhost" in url or "127.0.0.1" in url:
            return url
    if candidates:
        return candidates[-1]
    return ""


def _ensure_sslmode(url: str) -> str:
    if "render.com" in url and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}sslmode=require"
    return url


def _pg_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        for base in (Path(r"C:\Program Files\PostgreSQL"), Path(r"C:\Program Files (x86)\PostgreSQL")):
            if not base.is_dir():
                continue
            for ver in sorted(base.iterdir(), reverse=True):
                candidate = ver / "bin" / f"{name}.exe"
                if candidate.is_file():
                    return str(candidate)
    print(f"ERROR: no se encontró {name}. Instale PostgreSQL client tools.", file=sys.stderr)
    sys.exit(1)


def _pg_conn_env(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/") or "postgres"
    env = os.environ.copy()
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    env["PGDATABASE"] = dbname
    qs = parse_qs(parsed.query)
    if "sslmode" in qs:
        env["PGSSLMODE"] = qs["sslmode"][0]
    return env


def _run(cmd: list[str], env: dict[str, str], label: str) -> None:
    print(f"\n>> {label}")
    print("   ", " ".join(cmd[:6]), ("..." if len(cmd) > 6 else ""))
    subprocess.run(cmd, env=env, check=True)


def _sql(conn_env: dict[str, str], sql: str, psql: str) -> None:
    _run([psql, "-v", "ON_ERROR_STOP=1", "-c", sql], conn_env, "SQL en destino")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia esquema local a Render.")
    parser.add_argument("--schema", default=os.environ.get("DB_SCHEMA", "gestorVentas"))
    parser.add_argument("--yes", action="store_true", help="No pedir confirmación")
    parser.add_argument("--restore-only", metavar="DUMP", help="Solo restaurar un .dump ya creado")
    args = parser.parse_args()

    local_env = _load_env_file(ROOT / ".env")
    render_env = _load_env_file(ROOT / ".env.render")
    schema = (args.schema or "gestorVentas").strip()

    local_url = _pick_local_url({**local_env, **os.environ})
    render_url = (
        os.environ.get("DATABASE_URL")
        or render_env.get("DATABASE_URL")
        or ""
    ).strip()

    if not args.restore_only and not local_url:
        print("ERROR: defina LOCAL_DATABASE_URL o DATABASE_URL local en backend/.env", file=sys.stderr)
        sys.exit(1)
    if not render_url:
        print(
            "ERROR: defina DATABASE_URL de Render en backend/.env.render "
            "(External Database URL + ?sslmode=require)",
            file=sys.stderr,
        )
        sys.exit(1)

    render_url = _ensure_sslmode(render_url)
    local_env_vars = _pg_conn_env(local_url)
    render_env_vars = _pg_conn_env(render_url)

    local_hint = local_url.split("@")[-1] if local_url and "@" in local_url else "(solo restaurar)"
    render_hint = render_url.split("@")[-1].split("?")[0] if "@" in render_url else render_url
    print(f"Origen:  {local_hint}")
    print(f"Destino: {render_hint}")
    print(f"Esquema: {schema}")

    if not args.yes:
        answer = input(
            f'\nSe borrará el esquema "{schema}" en Render y se copiará desde local. ¿Continuar? [s/N]: '
        ).strip().lower()
        if answer not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            sys.exit(0)

    pg_dump = _pg_tool("pg_dump")
    pg_restore = _pg_tool("pg_restore")
    psql = _pg_tool("psql")

    if args.restore_only:
        dump_file = Path(args.restore_only)
        if not dump_file.is_file():
            print(f"ERROR: no existe {dump_file}", file=sys.stderr)
            sys.exit(1)
    else:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = BACKUPS / f"{schema}_{stamp}.dump"

        exclude_schemas = [s.strip() for s in (os.environ.get("PG_DUMP_EXCLUDE_SCHEMAS") or "helpmed,public").split(",") if s.strip()]
        dump_cmd = [
            pg_dump,
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(dump_file),
        ]
        for sch in exclude_schemas:
            dump_cmd.extend(["-N", sch])

        _run(
            dump_cmd,
            local_env_vars,
            f"Volcando local -> {dump_file.name}",
        )

    _sql(render_env_vars, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE;', psql)

    dbname = urlparse(render_url).path.lstrip("/") or "postgres"
    restore_cmd = [
        pg_restore,
        "--no-owner",
        "--no-acl",
        "--dbname",
        dbname,
        str(dump_file),
    ]
    print("\n>> Restaurando en Render")
    print("   ", " ".join(restore_cmd))
    result = subprocess.run(restore_cmd, env=render_env_vars, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode not in (0, 1):
        print(f"ERROR: pg_restore salió con código {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"\nListo. Copia guardada en: {dump_file}")
    print("Siguiente paso: redeploy del backend en Render (Start Command: bash scripts/render_start.sh).")


if __name__ == "__main__":
    main()
