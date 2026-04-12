from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentoventa",
            name="nubefact_enlace",
            field=models.CharField(
                blank=True,
                help_text="URL del PDF/XML devuelta por Nubefact tras emitir.",
                max_length=512,
            ),
        ),
    ]
