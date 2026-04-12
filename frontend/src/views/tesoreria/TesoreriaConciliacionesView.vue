<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Conciliaciones bancarias"
    tabla="conciliacion_bancaria"
    endpoint="/tesoreria/conciliaciones/"
    :columns="[
      { field: 'cuenta', label: 'Cuenta (id)' },
      { field: 'periodo', label: 'Periodo' },
      { field: 'saldo_libro', label: 'Saldo libro' },
      { field: 'saldo_banco', label: 'Saldo banco' },
      { field: 'cerrada', label: 'Cerrada' },
    ]"
  />
</template>
