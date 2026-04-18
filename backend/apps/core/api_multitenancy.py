"""
Aislamiento por empresa en la API (SaaS multi-tenant).

- Usuario con ``perfil_gestor``: solo datos de su ``empresa``.
- ``is_superuser``: en listados, sin filtro por empresa (visión global). En altas/imports
  que exijan ``empresa`` en el cuerpo o query, debe indicar el tenant explícitamente.
- Sin autenticar (p. ej. ``API_REQUIRE_AUTH=false`` en desarrollo): sin filtro, mismo
  comportamiento laxo que antes.
"""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied


def empresa_scope_for_request(request):
    """
    Retorna:
    - ``None``: no aplicar filtro (anónimo en dev, o superusuario).
    - ``-1``: usuario autenticado sin perfil (queryset vacío).
    - ``int``: ``empresa_id`` del tenant.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    perfil = getattr(user, "perfil_gestor", None)
    if perfil is None:
        return -1
    return int(perfil.empresa_id)


def filter_queryset_by_empresa(queryset, request, lookup: str = "empresa_id"):
    scope = empresa_scope_for_request(request)
    if scope is None:
        return queryset
    if scope == -1:
        return queryset.none()
    return queryset.filter(**{lookup: scope})


class EmpresaQuerysetMixin:
    """
    Solo filtra listados. Útil en modelos sin FK ``empresa`` (p. ej. líneas vía ``item``).

    ``empresa_lookup``: expresión ORM para ``filter()``, p. ej. ``item__empresa_id``.
    """

    empresa_lookup: str = "empresa_id"

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_empresa(qs, self.request, self.empresa_lookup)


class EmpresaScopedViewSetMixin(EmpresaQuerysetMixin):
    """
    Modelos con FK ``empresa`` (campo ``empresa_id`` en BD). Alta/edición fuerzan tenant.
    """

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            serializer.save()
            return
        if user.is_superuser:
            serializer.save()
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied(
                "Usuario sin empresa asignada. Contacte al administrador de la plataforma."
            )
        serializer.save(empresa_id=perfil.empresa_id)

    def perform_update(self, serializer):
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            serializer.save()
            return
        perfil = getattr(user, "perfil_gestor", None)
        if perfil is None:
            raise PermissionDenied(
                "Usuario sin empresa asignada. Contacte al administrador de la plataforma."
            )
        serializer.save(empresa_id=perfil.empresa_id)
