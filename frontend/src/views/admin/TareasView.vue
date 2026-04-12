<script setup lang="ts">
import MaestroApiList from '@/components/domain/MaestroApiList.vue'
</script>

<template>
  <MaestroApiList
    title="Mis tareas"
    tabla="tarea"
    endpoint="/administracion/tareas/"
    :columns="[
      { field: 'titulo', label: 'Título' },
      { field: 'completada', label: 'Hecha' },
      { field: 'fecha_limite', label: 'Límite' },
      { field: 'modulo', label: 'Módulo' },
    ]"
  />
</template>
