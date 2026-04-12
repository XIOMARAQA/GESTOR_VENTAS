"""One-off merge: schema_from_django_migrations + bootstrap → single SQL file."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
schema = (ROOT / "schema_from_django_migrations.sql").read_text(encoding="utf-8")
bootstrap = (ROOT / "docs/sql/00_bootstrap_core_tablas_postgresql.sql").read_text(encoding="utf-8")
bstart = bootstrap.find("BEGIN;")
bootstrap_sql = bootstrap[bstart:] if bstart != -1 else bootstrap

marker = "-- === administracion.0001_initial ==="
if marker not in schema:
    raise SystemExit("marker not found")
pre_admin, rest = schema.split(marker, 1)
pl = pre_admin.splitlines(keepends=True)
# Drop comment header lines before first migration block
start = 0
for i, line in enumerate(pl):
    if line.startswith("-- === "):
        start = i
        break
pre_admin_body = "".join(pl[start:])

new_header = (
    "-- =============================================================================\n"
    "-- Gestor_Ventas — ESQUEMA ÚNICO (referencia / DBeaver / PostgreSQL)\n"
    "-- Incluye: migraciones Django en orden + tablas core que core.0001 no crea en BD.\n"
    "-- Omita o adapte bloques marcados como operación Python sin equivalente SQL.\n"
    "-- Esquema 100 % alineado con producción: BD vacía + manage.py migrate + pg_dump --schema-only\n"
    "-- =============================================================================\n\n"
)

bootstrap_block = (
    "\n-- === bootstrap: empresa, sucursal, cliente, proveedor "
    "(no generado por core.0001) ===\n"
    + bootstrap_sql
    + "\n\n"
)

out = new_header + pre_admin_body + bootstrap_block + marker + rest

out = re.sub(
    r"-- === auth\.0006_require_contenttypes_0002 ===\s*python\.exe :.*?(?=-- === auth\.0007)",
    "-- === auth.0006_require_contenttypes_0002 ===\nBEGIN;\n-- (no SQL operations)\nCOMMIT;\n\n",
    out,
    count=1,
    flags=re.DOTALL,
)

out = out.replace(
    "    user_id              INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,\n"
    "    empresa_id           INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,\n"
    "    sucursal_default_id  INTEGER REFERENCES sucursal(id) ON DELETE SET NULL,",
    "    user_id              INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,\n"
    "    empresa_id           BIGINT NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,\n"
    "    sucursal_default_id  BIGINT REFERENCES sucursal(id) ON DELETE SET NULL,",
)

dest = ROOT / "docs/sql/gestor_ventas_esquema_completo.sql"
dest.write_text(out, encoding="utf-8")
print(f"Wrote {dest} ({len(out)} bytes)")
