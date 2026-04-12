<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Plan de cuentas"
    tabla="plan_cuenta"
    endpoint="/contabilidad/plan-cuentas/"
    :columns="[
      { field: 'codigo', label: 'Código' },
      { field: 'nombre', label: 'Nombre' },
      { field: 'tipo', label: 'Tipo' },
      { field: 'activo', label: 'Activo' },
    ]"
  />
</template>
