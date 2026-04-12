from django.contrib import admin

from apps.core.models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "razon_social",
        "ruc",
        "nombres",
        "telefono_contacto",
        "activo",
        "registro_aprobado",
        "creado_en",
    )
    list_filter = ("activo", "registro_aprobado")
    search_fields = ("razon_social", "ruc")
    ordering = ("-creado_en",)
    actions = ("aprobar_registro",)

    @admin.action(description="Aprobar registro (permitir acceso a la plataforma)")
    def aprobar_registro(self, request, queryset):
        updated = queryset.update(registro_aprobado=True)
        self.message_user(request, f"{updated} empresa(s) aprobada(s).")
