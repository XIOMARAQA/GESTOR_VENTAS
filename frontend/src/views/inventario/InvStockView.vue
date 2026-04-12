<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Stock por almacén"
    tabla="stock"
    endpoint="/inventario/stock/"
    :columns="[
      { field: 'item_nombre', label: 'Ítem' },
      { field: 'almacen_nombre', label: 'Almacén' },
      { field: 'cantidad', label: 'Cantidad' },
    ]"
  />
</template>
