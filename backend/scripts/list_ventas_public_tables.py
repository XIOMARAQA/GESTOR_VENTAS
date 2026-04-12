"""
Lista tablas en `public` relacionadas con ventas/cotización/comprobante.
Ejecutar desde la carpeta backend: python scripts/list_ventas_public_tables.py

Django (app ventas) usa por defecto ventas_cotizacion, ventas_documentoventa, etc.
Si también ves cotizacion / documento_venta sin prefijo, suelen ser tablas legacy;
no hace falta crear nuevas tablas para la funcionalidad actual del proyecto.
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection  # noqa: E402

with connection.cursor() as c:
    c.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND (
            table_name LIKE 'ventas_%'
            OR table_name IN (
              'cotizacion', 'cotizacion_linea',
              'documento_venta', 'documento_venta_linea',
              'pedido', 'pedido_linea'
            )
          )
        ORDER BY table_name
        """
    )
    rows = [r[0] for r in c.fetchall()]

for t in rows:
    print(t)
