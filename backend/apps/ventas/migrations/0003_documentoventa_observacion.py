from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0002_documentoventa_nubefact_enlace"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentoventa",
            name="observacion",
            field=models.TextField(blank=True),
        ),
    ]
