<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Comunicaciones de baja"
    tabla="comunicacion_baja"
    endpoint="/contabilidad/comunicaciones-baja/"
    :columns="[
      { field: 'fecha', label: 'Fecha' },
      { field: 'estado', label: 'Estado' },
      { field: 'descripcion', label: 'Descripción' },
    ]"
  />
</template>
