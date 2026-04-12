<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Atributos de ítem"
    tabla="atributo"
    endpoint="/inventario/atributos/"
    :columns="[{ field: 'nombre', label: 'Nombre' }, { field: 'empresa', label: 'Empresa (id)' }]"
  />
</template>
