<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Gastos recurrentes"
    tabla="gasto_recurrente"
    endpoint="/compras/gastos-recurrentes/"
    :columns="[
      { field: 'concepto', label: 'Concepto' },
      { field: 'monto', label: 'Monto' },
      { field: 'periodicidad', label: 'Periodicidad' },
      { field: 'activo', label: 'Activo' },
    ]"
  />
</template>
