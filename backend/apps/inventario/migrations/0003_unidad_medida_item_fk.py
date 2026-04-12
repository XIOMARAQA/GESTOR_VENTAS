# Catálogo unidad_medida + FK en item (migra el antiguo VARCHAR).

import django.db.models.deletion
from django.db import migrations, models


def forwards_migrar_unidades(apps, schema_editor):
    Item = apps.get_model("inventario", "Item")
    UnidadMedida = apps.get_model("inventario", "UnidadMedida")
    for item in Item.objects.all().iterator():
        raw = getattr(item, "unidad_medida", None)
        code = (raw or "UND").strip() if isinstance(raw, str) else "UND"
        if not code:
            code = "UND"
        code = code[:20]
        um, _ = UnidadMedida.objects.get_or_create(
            empresa_id=item.empresa_id,
            codigo=code,
            defaults={
                "nombre": code if len(code) > 3 else code.upper(),
                "codigo_close2u": "",
                "activo": True,
            },
        )
        Item.objects.filter(pk=item.pk).update(unidad_medida_nueva_id=um.pk)


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_empresa_persona_natural_contacto"),
        ("inventario", "0002_marca_y_item_marca"),
    ]

    operations = [
        migrations.CreateModel(
            name="UnidadMedida",
            fields=[
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "codigo",
                    models.CharField(
                        help_text="Código corto (p. ej. NIUB, UND, KG).",
                        max_length=20,
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                (
                    "codigo_close2u",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Código en integraciones tipo Close2u / facturación electrónica si aplica.",
                        max_length=80,
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unidades_medida",
                        to="core.empresa",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Unidades de medida",
                "ordering": ["codigo", "nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="unidadmedida",
            constraint=models.UniqueConstraint(
                fields=("empresa", "codigo"),
                name="uniq_unidad_medida_codigo_por_empresa",
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="unidad_medida_nueva",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventario.unidadmedida",
            ),
        ),
        migrations.RunPython(forwards_migrar_unidades, backwards_noop),
        migrations.RemoveField(
            model_name="item",
            name="unidad_medida",
        ),
        migrations.RenameField(
            model_name="item",
            old_name="unidad_medida_nueva",
            new_name="unidad_medida",
        ),
        migrations.AlterField(
            model_name="item",
            name="unidad_medida",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="items",
                to="inventario.unidadmedida",
            ),
        ),
    ]
