<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Asientos contables"
    tabla="asiento_contable"
    endpoint="/contabilidad/asientos/"
    :columns="[
      { field: 'fecha', label: 'Fecha' },
      { field: 'glosa', label: 'Glosa' },
      { field: 'origen_tipo', label: 'Origen' },
    ]"
  />
</template>
