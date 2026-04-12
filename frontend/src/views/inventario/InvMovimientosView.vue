<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Movimientos de inventario"
    tabla="movimiento_stock"
    endpoint="/inventario/movimientos/"
    :columns="[
      { field: 'tipo', label: 'Tipo' },
      { field: 'creado_en', label: 'Fecha' },
      { field: 'referencia_tipo', label: 'Ref. tipo' },
      { field: 'almacen', label: 'Almacén (id)' },
    ]"
  />
</template>
