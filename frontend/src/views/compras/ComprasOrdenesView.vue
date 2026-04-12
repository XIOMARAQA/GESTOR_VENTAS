<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Órdenes de compra"
    tabla="orden_compra"
    endpoint="/compras/ordenes/"
    :columns="[
      { field: 'numero', label: 'Número' },
      { field: 'fecha', label: 'Fecha' },
      { field: 'total', label: 'Total' },
      { field: 'estado', label: 'Estado' },
    ]"
  />
</template>
