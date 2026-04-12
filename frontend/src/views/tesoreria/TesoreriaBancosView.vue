<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <div class="stack">
    <MaestroApiList
      title="Cuentas bancarias"
      tabla="cuenta_bancaria"
      endpoint="/tesoreria/bancos/"
      :columns="[
        { field: 'banco', label: 'Banco' },
        { field: 'numero', label: 'Número' },
        { field: 'moneda', label: 'Moneda' },
        { field: 'saldo', label: 'Saldo' },
      ]"
    />
    <MaestroApiList
      title="Cajas"
      tabla="caja"
      endpoint="/tesoreria/cajas/"
      :columns="[
        { field: 'nombre', label: 'Nombre' },
        { field: 'sucursal', label: 'Sucursal (id)' },
        { field: 'activa', label: 'Activa' },
      ]"
    />
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
</style>
