<script setup lang="ts">
import axios from 'axios'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '@/api/client'
import { useAppContextStore } from '@/stores/appContext'
import { listLoadErrorMessage } from '@/utils/listLoadErrorMessage'

const CLAVE = 'nubefact_pdf_formatos'

type ConfigRow = {
  id: number
  empresa: number
  clave: string
  valor: Record<string, unknown>
}

type EmpresaDet = {
  id: number
  razon_social?: string
  ruc?: string
  telefono_contacto?: string
  logo_comprobante_url?: string | null
}

const MODELOS = [
  { value: 'a4_logo_izq', label: 'Modelo A4 — Logo a la izquierda' },
  { value: 'a4_logo_centro', label: 'Modelo A4 — Logo centrado' },
  { value: 'ticket', label: 'Modelo ticket (ancho reducido)' },
] as const

const FUENTES = ['Arial', 'Helvetica', 'Times New Roman', 'Georgia', 'Verdana'] as const

const DEFAULT_ESTILO = {
  factura: 'A4',
  boleta: 'TICKET',
  color_cabecera: '#1e40af',
  color_lineas: '#93c5fd',
  color_texto_cabecera: '#ffffff',
  modelo: 'a4_logo_izq',
  fuente: 'Arial',
} as const

const muestraLineas = [
  {
    item: 1,
    cant: '2',
    cod: 'SRV-001',
    desc: 'Servicio de monitoreo remoto',
    und: 'NIU',
    vu: '5,000.00',
    pu: '5,900.00',
    dscto: '0.00',
    vv: '10,000.00',
  },
  {
    item: 2,
    cant: '1',
    cod: 'EQ-12',
    desc: 'Kit de sensores',
    und: 'NIU',
    vu: '3,500.00',
    pu: '4,130.00',
    dscto: '0.00',
    vv: '3,500.00',
  },
]

const ctx = useAppContextStore()
const { empresaId, isSuperuser } = storeToRefs(ctx)

const loading = ref(true)
const saving = ref(false)
const uploadingLogo = ref(false)
const err = ref('')
const okMsg = ref('')
const configId = ref<number | null>(null)
const empresa = ref<EmpresaDet | null>(null)

const formatoFactura = ref<'A4' | 'TICKET'>('A4')
const formatoBoleta = ref<'A4' | 'TICKET'>('TICKET')
const colorCabecera = ref<string>(DEFAULT_ESTILO.color_cabecera)
const colorLineas = ref<string>(DEFAULT_ESTILO.color_lineas)
const colorTextoCabecera = ref<string>(DEFAULT_ESTILO.color_texto_cabecera)
const modeloComprobante = ref<string>(DEFAULT_ESTILO.modelo)
const fuente = ref<string>(DEFAULT_ESTILO.fuente)

const logoInput = ref<HTMLInputElement | null>(null)

const bloqueado = computed(() => isSuperuser.value && !empresaId.value)

const targetEmpresaId = computed(() => {
  const raw = empresaId.value
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
})

const fontStack = computed(() => {
  const f = fuente.value
  if (f === 'Times New Roman') return '"Times New Roman", Times, serif'
  if (f === 'Georgia') return 'Georgia, "Times New Roman", serif'
  if (f === 'Verdana') return 'Verdana, Geneva, sans-serif'
  if (f === 'Helvetica') return 'Helvetica, Arial, sans-serif'
  return 'Arial, "Helvetica Neue", Helvetica, sans-serif'
})

const previewVars = computed(() => ({
  '--cab': colorCabecera.value,
  '--lin': colorLineas.value,
  '--cab-txt': colorTextoCabecera.value,
  '--pdf-font': fontStack.value,
}))

const layoutMod = computed(() => {
  if (modeloComprobante.value === 'a4_logo_centro') return 'preview-sheet--center'
  if (modeloComprobante.value === 'ticket') return 'preview-sheet--ticket'
  return 'preview-sheet--left'
})

const logoSrc = computed(() => empresa.value?.logo_comprobante_url || null)

function drfMsg(data: unknown): string {
  if (data == null || typeof data !== 'object') return 'No se pudo guardar.'
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
  const parts: string[] = []
  for (const val of Object.values(d)) {
    if (Array.isArray(val)) {
      for (const x of val) {
        if (typeof x === 'string') parts.push(x)
      }
    }
  }
  return parts.join(' ') || 'No se pudo guardar.'
}

function mergeValor(raw: Record<string, unknown>) {
  const f = String(raw.factura ?? '').toUpperCase()
  const b = String(raw.boleta ?? '').toUpperCase()
  formatoFactura.value = f === 'TICKET' ? 'TICKET' : 'A4'
  formatoBoleta.value = b === 'A4' ? 'A4' : 'TICKET'
  colorCabecera.value =
    typeof raw.color_cabecera === 'string' && raw.color_cabecera ? raw.color_cabecera : DEFAULT_ESTILO.color_cabecera
  colorLineas.value =
    typeof raw.color_lineas === 'string' && raw.color_lineas ? raw.color_lineas : DEFAULT_ESTILO.color_lineas
  colorTextoCabecera.value =
    typeof raw.color_texto_cabecera === 'string' && raw.color_texto_cabecera
      ? raw.color_texto_cabecera
      : DEFAULT_ESTILO.color_texto_cabecera
  const m = String(raw.modelo ?? '')
  modeloComprobante.value = MODELOS.some((x) => x.value === m) ? m : DEFAULT_ESTILO.modelo
  const fn = String(raw.fuente ?? '')
  fuente.value = FUENTES.includes(fn as (typeof FUENTES)[number]) ? fn : DEFAULT_ESTILO.fuente
}

function buildValor(): Record<string, string> {
  return {
    factura: formatoFactura.value,
    boleta: formatoBoleta.value,
    color_cabecera: colorCabecera.value,
    color_lineas: colorLineas.value,
    color_texto_cabecera: colorTextoCabecera.value,
    modelo: modeloComprobante.value,
    fuente: fuente.value,
  }
}

async function load() {
  loading.value = true
  err.value = ''
  okMsg.value = ''
  if (bloqueado.value) {
    loading.value = false
    return
  }
  const eid = targetEmpresaId.value
  if (eid == null) {
    loading.value = false
    return
  }
  try {
    const [cfgRes, empRes] = await Promise.all([
      api.get<{ results?: ConfigRow[] } | ConfigRow[]>('/administracion/configuracion/?page_size=200'),
      api.get<EmpresaDet>(`/core/empresas/${eid}/`),
    ])
    empresa.value = empRes.data
    const list = Array.isArray(cfgRes.data) ? cfgRes.data : (cfgRes.data.results ?? [])
    const row = list.find((r) => r.clave === CLAVE && Number(r.empresa) === eid)
    configId.value = row?.id ?? null
    const v = row?.valor && typeof row.valor === 'object' ? (row.valor as Record<string, unknown>) : {}
    mergeValor(v)
  } catch (e) {
    err.value = listLoadErrorMessage(e, 'los datos')
    empresa.value = null
    configId.value = null
    mergeValor({})
  } finally {
    loading.value = false
  }
}

async function guardar() {
  if (bloqueado.value || targetEmpresaId.value == null) return
  saving.value = true
  err.value = ''
  okMsg.value = ''
  const valor = buildValor()
  const eid = targetEmpresaId.value
  try {
    if (configId.value != null) {
      await api.patch(`/administracion/configuracion/${configId.value}/`, { valor })
    } else {
      const body: Record<string, unknown> = { clave: CLAVE, valor }
      if (isSuperuser.value) {
        body.empresa = eid
      }
      const { data } = await api.post<ConfigRow>('/administracion/configuracion/', body)
      configId.value = data.id
    }
    okMsg.value =
      'Cambios guardados. Los colores, modelo y tipografía se usan en esta vista previa y quedan listos para futuras impresiones locales; el tamaño A4/ticket se envía a Nubefact al emitir.'
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'Error de conexión.'
    }
  } finally {
    saving.value = false
  }
}

function abrirSelectorLogo() {
  logoInput.value?.click()
}

async function onLogoSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const eid = targetEmpresaId.value
  if (!file || eid == null) return
  uploadingLogo.value = true
  err.value = ''
  okMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('logo_comprobante', file)
    const { data } = await api.patch<EmpresaDet>(`/core/empresas/${eid}/`, fd)
    empresa.value = data
    okMsg.value = 'Logo actualizado. Revise la vista previa.'
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data) {
      err.value = drfMsg(e.response.data)
    } else {
      err.value = 'No se pudo subir el logo.'
    }
  } finally {
    uploadingLogo.value = false
  }
}

onMounted(() => {
  void load()
})

watch([empresaId, isSuperuser], () => {
  void load()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <h1 class="title">Editar formato de comprobante</h1>
        <p class="lead">
          Ajuste colores, disposición del logo, tipografía y tamaño de página para
          <strong>facturas y boletas</strong>. La vista previa usa los datos de su empresa y líneas de ejemplo.
        </p>
      </div>
    </header>

    <p v-if="bloqueado" class="warn">
      Modo administrador global: elija una empresa en la barra superior para configurar el formato.
    </p>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="okMsg" class="ok">{{ okMsg }}</p>

    <div v-if="loading" class="card muted">Cargando…</div>

    <div v-else-if="!bloqueado && empresa" class="workspace">
      <aside class="panel panel--controls">
        <h2 class="panel__title">Personalización</h2>

        <div class="field">
          <span class="lab">Color de cabecera (tabla)</span>
          <div class="color-row">
            <input v-model="colorCabecera" type="color" class="color-inp" aria-label="Color de cabecera" />
            <input v-model="colorCabecera" type="text" class="inp inp--hex" maxlength="7" />
          </div>
        </div>

        <div class="field">
          <span class="lab">Color de líneas</span>
          <div class="color-row">
            <input v-model="colorLineas" type="color" class="color-inp" aria-label="Color de líneas" />
            <input v-model="colorLineas" type="text" class="inp inp--hex" maxlength="7" />
          </div>
        </div>

        <div class="field">
          <span class="lab">Color de letras en cabecera</span>
          <div class="color-row">
            <input v-model="colorTextoCabecera" type="color" class="color-inp" aria-label="Color texto cabecera" />
            <input v-model="colorTextoCabecera" type="text" class="inp inp--hex" maxlength="7" />
          </div>
        </div>

        <label class="field">
          <span class="lab">Modelo de comprobante</span>
          <select v-model="modeloComprobante" class="inp inp--select">
            <option v-for="m in MODELOS" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </label>

        <label class="field">
          <span class="lab">Tipo de letra</span>
          <select v-model="fuente" class="inp inp--select">
            <option v-for="f in FUENTES" :key="f" :value="f">{{ f }}</option>
          </select>
        </label>

        <div class="field field--logo">
          <span class="lab">Logo de la empresa</span>
          <div class="logo-box">
            <div v-if="logoSrc" class="logo-preview-wrap">
              <img :src="logoSrc" alt="Logo empresa" class="logo-preview" />
            </div>
            <div v-else class="logo-placeholder">Sin logo</div>
            <p class="logo-hint">
              Alto máx. recomendado 150 px · Ancho máx. recomendado 430 px · Formatos: .png, .jpg, .jpeg
            </p>
            <input
              ref="logoInput"
              type="file"
              class="sr-only"
              accept=".png,.jpg,.jpeg,image/png,image/jpeg"
              @change="onLogoSelected"
            />
            <button type="button" class="btn-cambiar" :disabled="uploadingLogo" @click="abrirSelectorLogo">
              {{ uploadingLogo ? 'Subiendo…' : 'Cambiar' }}
            </button>
          </div>
        </div>

        <div class="subsection">
          <h3 class="subsection__title">Tamaño PDF (Nubefact / SUNAT)</h3>
          <p class="subsection__txt">
            Se envía como <code>formato_de_pdf</code> al proveedor electrónico (A4 o ticket).
          </p>
          <label class="field">
            <span class="lab">Factura electrónica</span>
            <select v-model="formatoFactura" class="inp inp--select">
              <option value="A4">A4</option>
              <option value="TICKET">Ticket</option>
            </select>
          </label>
          <label class="field">
            <span class="lab">Boleta de venta</span>
            <select v-model="formatoBoleta" class="inp inp--select">
              <option value="TICKET">Ticket</option>
              <option value="A4">A4</option>
            </select>
          </label>
        </div>

        <button type="button" class="btn-save" :disabled="saving" @click="guardar">
          {{ saving ? 'Guardando…' : 'Guardar cambios' }}
        </button>
      </aside>

      <section class="panel panel--preview">
        <h2 class="panel__title">Vista previa</h2>
        <div class="preview-scroll">
          <div class="preview-sheet" :class="layoutMod" :style="previewVars">
            <div class="inv-head">
              <img v-if="logoSrc" :src="logoSrc" class="inv-logo" alt="" />
              <div class="inv-company">
                <strong class="inv-name">{{ empresa.razon_social?.trim() || 'Razón social' }}</strong>
                <p class="inv-meta">
                  Jr. Los Negocios N° 123 — Lima, Perú<br />
                  Telf.: {{ empresa.telefono_contacto?.trim() || '01 234 5678' }} · contacto@empresa.com.pe
                </p>
              </div>
              <div class="inv-fiscal">
                <div class="inv-fiscal__ruc">RUC {{ empresa.ruc?.trim() || '20123456789' }}</div>
                <div class="inv-fiscal__tipo">FACTURA ELECTRÓNICA</div>
                <div class="inv-fiscal__num">F001-00000123</div>
              </div>
            </div>

            <div class="inv-block">
              <div class="inv-row2">
                <span class="k">Señores:</span>
                <span class="v">Cliente de ejemplo S.A.C.</span>
              </div>
              <div class="inv-row2">
                <span class="k">Dirección:</span>
                <span class="v">Av. Ejemplo 456 — San Isidro</span>
              </div>
              <div class="inv-grid4">
                <div><span class="k">RUC:</span> 20555666777</div>
                <div><span class="k">Forma de pago:</span> Crédito</div>
                <div><span class="k">Fecha emisión:</span> 12/04/2026</div>
                <div><span class="k">Moneda:</span> USD</div>
              </div>
            </div>

            <table class="inv-table">
              <thead>
                <tr>
                  <th>Ítem</th>
                  <th>Cant.</th>
                  <th>Código</th>
                  <th>Descripción</th>
                  <th>Und.</th>
                  <th>V.U.</th>
                  <th>P.U.</th>
                  <th>Dscto.</th>
                  <th>Valor venta</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ln in muestraLineas" :key="ln.item">
                  <td>{{ ln.item }}</td>
                  <td>{{ ln.cant }}</td>
                  <td>{{ ln.cod }}</td>
                  <td class="td-desc">{{ ln.desc }}</td>
                  <td>{{ ln.und }}</td>
                  <td class="td-num">{{ ln.vu }}</td>
                  <td class="td-num">{{ ln.pu }}</td>
                  <td class="td-num">{{ ln.dscto }}</td>
                  <td class="td-num">{{ ln.vv }}</td>
                </tr>
              </tbody>
            </table>

            <div class="inv-totals">
              <div class="tot-line"><span>Total venta gravada</span><span>13,500.00</span></div>
              <div class="tot-line"><span>Total IGV</span><span>2,430.00</span></div>
              <div class="tot-line tot-line--strong"><span>Importe total de la venta</span><span>15,930.00</span></div>
            </div>

            <p class="inv-words">
              SON: QUINCE MIL NOVECIENTOS TREINTA Y 00/100 DÓLARES AMERICANOS
            </p>
            <p class="inv-legal">
              Representación impresa de la factura electrónica · Autorizado mediante Resolución de Superintendencia
            </p>
          </div>
        </div>
        <p class="preview-foot">
          El PDF oficial SUNAT lo genera <strong>Nubefact</strong> con el tamaño A4 o ticket indicado arriba. Esta vista
          previa muestra cómo se verán marca, colores y tipografía en documentos impresos o futuras plantillas locales
          del proyecto.
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 1280px;
  color: #0f172a;
}

.head {
  margin-bottom: 1rem;
}

.title {
  margin: 0 0 0.35rem;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.55;
  max-width: 52rem;
}

.lead strong {
  color: #334155;
}

.warn {
  font-size: 0.85rem;
  color: #9a3412;
  background: #ffedd5;
  border: 1px solid #fdba74;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  margin: 0 0 0.75rem;
}

.err {
  color: #991b1b;
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.75rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.ok {
  color: #166534;
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.75rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
}

.card.muted {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.workspace {
  display: grid;
  gap: 1.25rem;
  align-items: start;
}

@media (min-width: 1024px) {
  .workspace {
    grid-template-columns: minmax(280px, 340px) 1fr;
  }
}

.panel {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgb(15 23 42 / 6%);
}

.panel--controls {
  padding: 1.15rem 1.2rem 1.35rem;
}

.panel--preview {
  padding: 1rem 1rem 1.15rem;
  min-width: 0;
}

.panel__title {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.9rem;
}

.field--logo {
  margin-bottom: 1.1rem;
}

.lab {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.color-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.color-inp {
  width: 2.75rem;
  height: 2.25rem;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  cursor: pointer;
}

.inp {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.875rem;
  font-family: inherit;
}

.inp--hex {
  flex: 1;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
}

.inp--select {
  cursor: pointer;
}

.logo-box {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 0.75rem;
  background: #f8fafc;
}

.logo-preview-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 4rem;
  margin-bottom: 0.5rem;
}

.logo-preview {
  max-height: 100px;
  max-width: 100%;
  object-fit: contain;
}

.logo-placeholder {
  text-align: center;
  color: #94a3b8;
  font-size: 0.85rem;
  padding: 1.25rem;
}

.logo-hint {
  margin: 0 0 0.65rem;
  font-size: 0.72rem;
  color: #64748b;
  line-height: 1.45;
}

.btn-cambiar {
  display: inline-block;
  padding: 0.4rem 0.9rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #fff;
  color: #0f766e;
  font-weight: 700;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  font-family: inherit;
}

.btn-cambiar:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.subsection {
  margin: 1.15rem 0 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.subsection__title {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: #334155;
}

.subsection__txt {
  margin: 0 0 0.65rem;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.45;
}

.subsection__txt code {
  font-size: 0.72rem;
  background: #f1f5f9;
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
}

.btn-save {
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  border: 1px solid #0e7490;
  background: #0e7490;
  color: #fff;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  font-family: inherit;
}

.btn-save:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.preview-scroll {
  overflow: auto;
  max-height: min(78vh, 920px);
  padding: 0.5rem;
  background: #e2e8f0;
  border-radius: 10px;
}

.preview-sheet {
  --cab: #1e40af;
  --lin: #93c5fd;
  --cab-txt: #ffffff;
  --pdf-font: Arial, sans-serif;
  margin: 0 auto;
  background: #fff;
  padding: 1.1rem 1.25rem 1.25rem;
  box-shadow: 0 4px 24px rgb(15 23 42 / 10%);
  font-family: var(--pdf-font);
  font-size: 0.72rem;
  color: #0f172a;
  max-width: 640px;
}

.preview-sheet--ticket {
  max-width: 280px;
  font-size: 0.62rem;
  padding: 0.65rem 0.75rem;
}

.preview-sheet--ticket .inv-table th,
.preview-sheet--ticket .inv-table td {
  padding: 0.2rem 0.15rem;
  font-size: 0.55rem;
}

.preview-sheet--ticket .inv-head {
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.preview-sheet--ticket .inv-fiscal {
  width: 100%;
  margin-top: 0.5rem;
}

.inv-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.75rem 1rem;
  margin-bottom: 0.85rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--lin);
}

.preview-sheet--center .inv-head {
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.preview-sheet--center .inv-company {
  text-align: center;
}

.preview-sheet--left .inv-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: start;
}

@media (max-width: 520px) {
  .preview-sheet--left .inv-head {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }
}

.inv-logo {
  max-height: 72px;
  max-width: 160px;
  object-fit: contain;
}

.preview-sheet--ticket .inv-logo {
  max-height: 48px;
  max-width: 120px;
}

.inv-company {
  flex: 1;
  min-width: 0;
}

.inv-name {
  display: block;
  font-size: 0.95rem;
  margin-bottom: 0.25rem;
}

.preview-sheet--ticket .inv-name {
  font-size: 0.75rem;
}

.inv-meta {
  margin: 0;
  color: #475569;
  line-height: 1.4;
  font-size: 0.68rem;
}

.inv-fiscal {
  border: 1px solid var(--lin);
  padding: 0.45rem 0.55rem;
  text-align: center;
  min-width: 7.5rem;
}

.inv-fiscal__ruc {
  font-weight: 700;
  font-size: 0.7rem;
}

.inv-fiscal__tipo {
  font-weight: 800;
  font-size: 0.62rem;
  margin: 0.2rem 0;
  color: #0f172a;
}

.inv-fiscal__num {
  font-weight: 700;
  font-size: 0.75rem;
}

.inv-block {
  margin-bottom: 0.65rem;
  font-size: 0.68rem;
}

.inv-row2 {
  display: grid;
  grid-template-columns: 5.5rem 1fr;
  gap: 0.35rem;
  margin-bottom: 0.25rem;
}

.inv-grid4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem 0.75rem;
  margin-top: 0.4rem;
}

.k {
  color: #64748b;
  font-weight: 600;
}

.inv-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.65rem;
}

.inv-table th {
  background: var(--cab);
  color: var(--cab-txt);
  font-weight: 700;
  text-align: left;
  padding: 0.35rem 0.3rem;
  font-size: 0.62rem;
  border: 1px solid var(--cab);
}

.inv-table td {
  padding: 0.32rem 0.3rem;
  border-bottom: 1px solid var(--lin);
  vertical-align: top;
}

.td-desc {
  max-width: 8rem;
}

.td-num {
  text-align: right;
  white-space: nowrap;
}

.inv-totals {
  margin-left: auto;
  max-width: 14rem;
  font-size: 0.7rem;
}

.tot-line {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid #e2e8f0;
}

.tot-line--strong {
  font-weight: 800;
  border-bottom: none;
  margin-top: 0.15rem;
}

.inv-words {
  margin: 0.65rem 0 0.35rem;
  font-size: 0.65rem;
  font-weight: 600;
  color: #334155;
  line-height: 1.4;
}

.inv-legal {
  margin: 0;
  font-size: 0.58rem;
  color: #64748b;
  line-height: 1.35;
}

.preview-foot {
  margin: 0.75rem 0 0;
  font-size: 0.72rem;
  color: #64748b;
  line-height: 1.45;
  max-width: 42rem;
}

.preview-foot strong {
  color: #475569;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
</style>
