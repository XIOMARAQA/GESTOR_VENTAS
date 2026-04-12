from django.contrib import admin

from .models import UnidadMedida


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "codigo_sunat", "activo", "empresa")
    list_filter = ("activo", "empresa")
    search_fields = ("codigo", "nombre", "codigo_sunat")
    ordering = ("empresa", "codigo")
