from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_perfil_usuario_sql"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="direccion",
            field=models.TextField(blank=True),
        ),
    ]
