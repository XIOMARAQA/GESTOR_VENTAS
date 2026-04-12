<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Configuración del sistema"
    tabla="configuracion_sistema"
    endpoint="/administracion/configuracion/"
    :columns="[
      { field: 'clave', label: 'Clave' },
      { field: 'empresa', label: 'Empresa (id)' },
      { field: 'valor', label: 'Valor (JSON)' },
    ]"
  />
</template>
