"""
Mueve las tablas de Gestor de Ventas desde `public` al esquema dedicado (p. ej. gestorVentas).

Uso (desde backend/, con el servidor detenido o tras reiniciarlo):
  python manage.py migrar_esquema_gestor_ventas --dry-run
  python manage.py migrar_esquema_gestor_ventas --yes

Requisitos: PostgreSQL. No toca el esquema helpmed ni otras apps en public que no sean de este proyecto.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


def _quoted_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _tables_in_schema(schema: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = %s
            ORDER BY tablename
            """,
            [schema],
        )
        return [row[0] for row in cursor.fetchall()]


def _row_count(schema: str, table: str) -> int:
    q_schema = _quoted_ident(schema)
    q_table = _quoted_ident(table)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {q_schema}.{q_table}")
        return int(cursor.fetchone()[0])


def _schema_exists(schema: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM pg_namespace WHERE nspname = %s
            """,
            [schema],
        )
        return cursor.fetchone() is not None


class Command(BaseCommand):
    help = "Mueve tablas de Gestor de Ventas de public al esquema gestorVentas conservando datos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            default=getattr(settings, "DB_SCHEMA", "gestorVentas"),
            help='Esquema destino (default: DB_SCHEMA o "gestorVentas").',
        )
        parser.add_argument(
            "--source",
            default="public",
            help='Esquema origen (default: "public").',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué tablas se moverían, sin ejecutar.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirma la migración física de tablas.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Este comando solo aplica a PostgreSQL.")

        target = (options["schema"] or "gestorVentas").strip()
        source = (options["source"] or "public").strip()
        dry_run = options["dry_run"]
        confirmed = options["yes"]

        if not dry_run and not confirmed:
            raise CommandError(
                "Añade --yes para ejecutar la migración o --dry-run para simular."
            )

        expected = self._expected_gestor_tables()
        in_source = set(_tables_in_schema(source))
        in_target = set(_tables_in_schema(target))

        to_move = sorted(expected & in_source)
        already = sorted(expected & in_target)
        missing = sorted(expected - in_source - in_target)

        self.stdout.write(self.style.NOTICE(f"Origen: {source} -> Destino: {target}"))
        self.stdout.write(f"Tablas del proyecto a ubicar en {target}: {len(expected)}")
        self.stdout.write(f"  En {source} (mover): {len(to_move)}")
        self.stdout.write(f"  Ya en {target}: {len(already)}")
        if missing:
            self.stdout.write(
                self.style.WARNING(f"  Sin ubicar (¿migraciones pendientes?): {len(missing)}")
            )
            for t in missing:
                self.stdout.write(f"    - {t}")

        if not to_move:
            if already and len(already) == len(expected):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Todas las tablas ya están en {_quoted_ident(target)}."
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No hay tablas que mover desde el origen."))
            return

        self.stdout.write("\nTablas a mover:")
        for t in to_move:
            try:
                rows = _row_count(source, t)
                self.stdout.write(f"  - {t} ({rows} filas)")
            except Exception:
                self.stdout.write(f"  - {t}")

        if dry_run:
            self.stdout.write(self.style.NOTICE("\nModo simulación: no se ejecutaron cambios."))
            return

        q_target = _quoted_ident(target)
        q_source = _quoted_ident(source)

        with transaction.atomic():
            with connection.cursor() as cursor:
                if not _schema_exists(target):
                    self.stdout.write(f"Creando esquema {q_target}...")
                    cursor.execute(f"CREATE SCHEMA {q_target}")

                db_user = settings.DATABASES["default"].get("USER") or "postgres"
                cursor.execute(f"GRANT ALL ON SCHEMA {q_target} TO {_quoted_ident(db_user)}")
                cursor.execute(f"GRANT USAGE ON SCHEMA {q_target} TO {_quoted_ident(db_user)}")

                for table in to_move:
                    q_table = _quoted_ident(table)
                    self.stdout.write(f"Moviendo {source}.{table} -> {target}.{table}...")
                    cursor.execute(
                        f"ALTER TABLE {q_source}.{q_table} SET SCHEMA {q_target}"
                    )

        self.stdout.write(self.style.SUCCESS("\nMigración de esquema completada."))
        self.stdout.write(
            "Reinicia runserver y verifica: python manage.py db_audit_tablas"
        )

        self._verify_counts(source, target, to_move)

    def _expected_gestor_tables(self) -> set[str]:
        from django.apps import apps

        tables = {"django_migrations"}
        for model in apps.get_models(include_auto_created=True):
            tables.add(model._meta.db_table)
        return tables

    def _verify_counts(self, source: str, target: str, moved: list[str]) -> None:
        self.stdout.write("\nVerificación de filas (destino):")
        for table in moved:
            try:
                rows = _row_count(target, table)
                self.stdout.write(f"  {target}.{table}: {rows} filas")
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  {target}.{table}: error al contar ({exc})")
                )
