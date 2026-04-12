<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <div class="stack">
    <MaestroApiList
      title="Empresas"
      subtitle="Listado de empresas registradas. «Activo» y «Reg. aprobado» indican si la empresa puede operar en el sistema."
      tabla="empresa"
      :show-tabla-meta="false"
      :show-refresh="true"
      empty-text="No hay empresas registradas o no tiene permiso para verlas."
      endpoint="/core/empresas/"
      :columns="[
        { field: 'razon_social', label: 'Razón social' },
        { field: 'ruc', label: 'RUC' },
        { field: 'activo', label: 'Activo' },
        { field: 'registro_aprobado', label: 'Reg. aprobado' },
      ]"
    />
    <MaestroApiList
      title="Sucursales"
      subtitle="Locales o puntos de venta. Cada fila pertenece a la empresa indicada en la columna Empresa."
      tabla="sucursal"
      :show-tabla-meta="false"
      :show-refresh="true"
      empty-text="No hay sucursales o no tiene permiso para verlas."
      endpoint="/core/sucursales/"
      :columns="[
        { field: 'nombre', label: 'Nombre' },
        { field: 'empresa_razon_social', label: 'Empresa' },
        { field: 'activo', label: 'Activo' },
      ]"
    />
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
</style>
