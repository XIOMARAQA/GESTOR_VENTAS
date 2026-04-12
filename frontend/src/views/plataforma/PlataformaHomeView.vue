<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '@/api/client'

type Resumen = {
  empresas_total?: number
  empresas_activas_y_aprobadas?: number
  empresas_pendientes_aprobacion?: number
  empresas_inactivas?: number
  superusuarios_activos?: number
}

const loading = ref(true)
const err = ref('')
const data = ref<Resumen | null>(null)

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data: d } = await api.get<Resumen>('/core/plataforma/resumen/')
    data.value = d
  } catch {
    err.value = 'No pudimos cargar el resumen. Revise su conexión e intente otra vez.'
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <h1 class="title">Resumen de la plataforma</h1>
      <p class="lead">
        Cifras globales de clientes (empresas) y del equipo con acceso total. Para revisar ventas,
        stock u otros datos de un negocio, abra la empresa correspondiente y use su panel interno.
      </p>
    </header>

    <p v-if="err" class="err">{{ err }}</p>

    <div v-if="loading" class="muted">Cargando datos…</div>

    <template v-else-if="data">
      <div class="kpi-grid">
        <RouterLink to="/plataforma/empresas/activas" class="kpi kpi--link">
          <span class="kpi-label">Empresas activas</span>
          <span class="kpi-val">{{ data.empresas_activas_y_aprobadas ?? 0 }}</span>
          <span class="kpi-hint">Ver lista y entrar al sistema de cada cliente</span>
        </RouterLink>
        <RouterLink to="/plataforma/empresas/pendientes" class="kpi kpi--link kpi--warn">
          <span class="kpi-label">Pendientes de aprobación</span>
          <span class="kpi-val">{{ data.empresas_pendientes_aprobacion ?? 0 }}</span>
          <span class="kpi-hint">Revisar solicitudes de alta</span>
        </RouterLink>
        <RouterLink to="/plataforma/empresas/inactivas" class="kpi kpi--link kpi--muted">
          <span class="kpi-label">Suspendidas / inactivas</span>
          <span class="kpi-val">{{ data.empresas_inactivas ?? 0 }}</span>
          <span class="kpi-hint">Consultar empresas fuera de servicio</span>
        </RouterLink>
        <div class="kpi">
          <span class="kpi-label">Total de empresas</span>
          <span class="kpi-val">{{ data.empresas_total ?? 0 }}</span>
        </div>
        <RouterLink to="/plataforma/equipo" class="kpi kpi--link">
          <span class="kpi-label">Superusuarios activos</span>
          <span class="kpi-val">{{ data.superusuarios_activos ?? 0 }}</span>
          <span class="kpi-hint">Alta, edición y baja lógica</span>
        </RouterLink>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 960px;
}

.head {
  margin-bottom: 1.5rem;
}

.title {
  margin: 0 0 0.5rem;
  font-size: 1.45rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.55;
  color: #64748b;
  max-width: 42rem;
}

.lead strong {
  color: #334155;
  font-weight: 600;
}

.err {
  color: #b91c1c;
  font-size: 0.875rem;
  margin: 0 0 1rem;
}

.muted {
  color: #94a3b8;
  padding: 2rem 0;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.kpi {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.1rem 1.15rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 6%);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.kpi--link {
  text-decoration: none;
  color: inherit;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.kpi--link:hover {
  border-color: rgba(14, 116, 144, 0.45);
  box-shadow: 0 4px 14px rgb(14 116 144 / 10%);
}

.kpi--warn .kpi-val {
  color: #c2410c;
}

.kpi--muted .kpi-val {
  color: #64748b;
}

.kpi-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.kpi-val {
  font-size: 1.75rem;
  font-weight: 800;
  color: #0e7490;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.kpi-hint {
  font-size: 0.75rem;
  color: #0e7490;
  font-weight: 600;
  margin-top: 0.25rem;
}
</style>
