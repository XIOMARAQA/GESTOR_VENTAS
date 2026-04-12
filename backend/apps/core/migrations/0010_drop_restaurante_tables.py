from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_vendedor_y_comprobante_campos"),
    ]

    operations = [
        migrations.RunSQL(
            """
            DROP TABLE IF EXISTS restaurante_comandalinea CASCADE;
            DROP TABLE IF EXISTS restaurante_comanda CASCADE;
            DELETE FROM django_migrations WHERE app = 'restaurante';
            """,
            migrations.RunSQL.noop,
        ),
    ]
