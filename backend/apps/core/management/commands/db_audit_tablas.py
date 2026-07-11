"""
Audita tablas en la base de datos frente a los modelos Django instalados.

Uso:
  python manage.py db_audit_tablas
  python manage.py db_audit_tablas --sql-drop       # imprime DROP (no ejecuta)
  python manage.py db_audit_tablas --execute-drop --yes  # ejecuta DROP (solo PostgreSQL)

Las tablas listadas como "huérfanas" no tienen un modelo actual en INSTALLED_APPS.
Antes de ejecutar DROP: respaldo completo (pg_dump). Si hay datos solo en tablas
legadas sin prefijo (p. ej. `item`) y la app usa `inventario_item`, hay que migrar
datos, no solo borrar.
"""

from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


def _db_schema() -> str:
    return getattr(settings, "DB_SCHEMA", "public") or "public"


def _tables_in_db() -> list[str]:
    vendor = connection.vendor
    schema = _db_schema()
    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = %s
                ORDER BY tablename
                """,
                [schema],
            )
            return [r[0] for r in cursor.fetchall()]
        if vendor == "sqlite":
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            return [r[0] for r in cursor.fetchall()]
        raise SystemExit(f"Motor no soportado para auditoría: {vendor}")


def _estimated_rows_postgres(table: str) -> int | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(s.n_live_tup::bigint, -1)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_all_tables s ON s.relid = c.oid
            WHERE n.nspname = %s AND c.relkind = 'r' AND c.relname = %s
            """,
            [_db_schema(), table],
        )
        row = cursor.fetchone()
        if not row:
            return None
        v = row[0]
        return int(v) if v is not None else None


# Tablas que Django usa pero no exponen como Model en get_models()
_TABLAS_SISTEMA_DJANGO = frozenset({"django_migrations"})


def _expected_model_tables() -> set[str]:
    out: set[str] = set(_TABLAS_SISTEMA_DJANGO)
    for model in apps.get_models(include_auto_created=True):
        out.add(model._meta.db_table)
    return out


class Command(BaseCommand):
    help = "Compara tablas de la BD con modelos Django; opcionalmente genera SQL DROP para huérfanas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sql-drop",
            action="store_true",
            help="Imprime sentencias DROP TABLE ... CASCADE (no las ejecuta).",
        )
        parser.add_argument(
            "--execute-drop",
            action="store_true",
            help="Elimina tablas huérfanas (requiere --yes; solo PostgreSQL).",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirmación explícita tras backup.",
        )

    def handle(self, *args, **options):
        expected = _expected_model_tables()
        actual = set(_tables_in_db())

        missing = sorted(expected - actual)
        orphans = sorted(actual - expected)

        self.stdout.write(self.style.NOTICE("=== Tablas esperadas por Django (modelos) ==="))
        self.stdout.write(f"Total: {len(expected)}")

        self.stdout.write(self.style.NOTICE("\n=== Tablas en la base de datos ==="))
        self.stdout.write(f"Total: {len(actual)}")

        if missing:
            self.stdout.write(
                self.style.WARNING(
                    "\n--- Faltan en la BD (¿migraciones sin aplicar?) ---"
                )
            )
            for t in missing:
                self.stdout.write(f"  - {t}")

        if orphans:
            self.stdout.write(
                self.style.WARNING(
                    "\n--- Huérfanas: en la BD pero sin modelo Django actual ---"
                )
            )
            for t in orphans:
                extra = ""
                if connection.vendor == "postgresql":
                    est = _estimated_rows_postgres(t)
                    if est is not None and est >= 0:
                        extra = f"  (~{est} filas estimadas)"
                self.stdout.write(f"  - {t}{extra}")

            self.stdout.write(
                "\nSuele ser esquema antiguo duplicado (sin prefijo app_label): "
                "categoria/item vs inventario_*, caja/cobranza vs tesoreria_*, "
                "asiento_* vs contabilidad_asiento*, cotizacion vs ventas_cotizacion, "
                "rol/usuario_rol sin modelo en el proyecto."
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo hay tablas huérfanas detectadas."))

        if options["sql_drop"] and orphans:
            self.stdout.write(
                self.style.ERROR(
                    "\n-- Copia solo tras pg_dump / backup. Revisa filas estimadas arriba."
                )
            )
            self.stdout.write("BEGIN;")
            # Orden alfabético inverso reduce a veces dependencias; CASCADE cubre el resto.
            for t in sorted(orphans, reverse=True):
                self.stdout.write(f'DROP TABLE IF EXISTS "{t}" CASCADE;')
            self.stdout.write("COMMIT;")

        if options["execute_drop"]:
            if not options["yes"]:
                raise CommandError(
                    "Añade --yes para confirmar que tienes backup "
                    "(python manage.py db_audit_tablas --execute-drop --yes)."
                )
            if connection.vendor != "postgresql":
                raise CommandError(
                    "--execute-drop solo está implementado para PostgreSQL."
                )
            if not orphans:
                self.stdout.write(self.style.SUCCESS("No hay tablas huérfanas; nada que borrar."))
                return
            ordered = sorted(orphans, reverse=True)
            self.stdout.write(
                self.style.WARNING(
                    f"Eliminando {len(ordered)} tablas huérfanas con CASCADE…"
                )
            )
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Bloquear escrituras en esas tablas mientras se eliminan.
                    for t in ordered:
                        cursor.execute(
                            'DROP TABLE IF EXISTS "%s" CASCADE;' % t.replace('"', '')
                        )
            self.stdout.write(self.style.SUCCESS("Listo. Verifica con: python manage.py db_audit_tablas"))
