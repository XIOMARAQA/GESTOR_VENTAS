<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Pedidos"
    tabla="pedido"
    endpoint="/ventas/pedidos/"
    :columns="[
      { field: 'origen', label: 'Origen' },
      { field: 'estado', label: 'Estado' },
      { field: 'referencia_externa', label: 'Ref. externa' },
      { field: 'creado_en', label: 'Creado' },
    ]"
  />
</template>
