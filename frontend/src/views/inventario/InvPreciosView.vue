<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Listas de precio"
    tabla="lista_precio"
    endpoint="/inventario/listas-precio/"
    :columns="[
      { field: 'nombre', label: 'Nombre' },
      { field: 'moneda', label: 'Moneda' },
      { field: 'activa', label: 'Activa' },
    ]"
  />
</template>
