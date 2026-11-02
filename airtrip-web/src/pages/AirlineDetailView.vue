<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { AirlineDetail, Route } from '@/api/types'

const route = useRoute()
const iata = computed(() => String(route.params.iata ?? '').toUpperCase())

const detail = ref<AirlineDetail | null>(null)
const detailLoading = ref(true)
const detailError = ref('')

const filters = reactive({ origin: '', destination: '' })
const page = ref(1)
const pageSize = ref(10)
const rows = ref<Route[]>([])
const total = ref(0)
const pages = ref(1)
const loading = ref(false)
const error = ref('')

const columns: AeroColumn[] = [
  { key: 'route_id', label: 'Route ID', width: '92px', align: 'right', mono: true },
  { key: 'origin_iata', label: 'Origin', width: '110px' },
  { key: 'destination_iata', label: 'Destination', width: '110px' },
  { key: 'stops', label: 'Stops', width: '96px' },
  { key: 'equipment', label: 'Equipment', width: '120px', mono: true },
]

const queryKey = computed(() =>
  [filters.origin, filters.destination, page.value, pageSize.value].join('|'),
)

let timer: number | undefined
let routesSeq = 0

async function loadDetail(): Promise<void> {
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    detail.value = await api.airline(iata.value)
  } catch (err) {
    detailError.value = err instanceof ApiError ? err.message : 'Could not load this airline.'
  } finally {
    detailLoading.value = false
  }
}

async function loadRoutes(): Promise<void> {
  if (!detail.value) return
  const seq = ++routesSeq
  loading.value = true
  error.value = ''
  try {
    const result = await api.airlineRoutes(iata.value, {
      origin: filters.origin.trim().toUpperCase() || undefined,
      destination: filters.destination.trim().toUpperCase() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    if (seq !== routesSeq) return
    rows.value = result.items
    total.value = result.total
    pages.value = Math.max(1, result.pages)
    if (page.value > pages.value) page.value = pages.value
  } catch (err) {
    if (seq !== routesSeq) return
    error.value = err instanceof ApiError ? err.message : 'Could not load routes.'
    rows.value = []
    total.value = 0
    pages.value = 1
  } finally {
    if (seq === routesSeq) loading.value = false
  }
}

watch(
  iata,
  () => {
    filters.origin = ''
    filters.destination = ''
    page.value = 1
    routesSeq += 1
    loading.value = false
    rows.value = []
    total.value = 0
    pages.value = 1
    void loadDetail()
  },
  { immediate: true },
)

watch(detail, (value) => {
  if (value) void loadRoutes()
})

watch(
  queryKey,
  () => {
    if (!detail.value) return
    window.clearTimeout(timer)
    timer = window.setTimeout(loadRoutes, 220)
  },
)

watch(
  () => [filters.origin, filters.destination].join('|'),
  () => {
    if (page.value !== 1) page.value = 1
  },
)

watch(
  () => filters.origin,
  (value) => {
    const next = value.toUpperCase()
    if (next !== value) filters.origin = next
  },
)

watch(
  () => filters.destination,
  (value) => {
    const next = value.toUpperCase()
    if (next !== value) filters.destination = next
  },
)

onBeforeUnmount(() => window.clearTimeout(timer))

function reset(): void {
  filters.origin = ''
  filters.destination = ''
  page.value = 1
}

function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}
</script>

<template>
  <div v-if="detailLoading && !detail" class="grid gap-4">
    <div class="tile h-[92px] animate-pulse" />
    <div class="grid grid-cols-2 gap-3 sm:max-w-[520px]">
      <div class="tile h-[86px] animate-pulse" />
      <div class="tile h-[86px] animate-pulse" />
    </div>
  </div>

  <template v-else-if="detailError && !detail">
    <AeroWindow title="Airline unavailable">
      <AeroEmpty :title="`Could not load ${iata}`" :text="detailError">
        <div class="mt-2 flex flex-wrap justify-center gap-2">
          <button class="btn btn-sm" @click="loadDetail">
            <span class="btn-label"><AeroIcon name="refresh" :size="12" /> Retry</span>
          </button>
          <RouterLink to="/airlines" class="btn btn-sm btn-glass">
            <span class="btn-label"><AeroIcon name="chevron-left" :size="12" /> All airlines</span>
          </RouterLink>
        </div>
      </AeroEmpty>
    </AeroWindow>
  </template>

  <template v-else-if="detail">
    <AeroPageHeader
      eyebrow="Airline"
      :title="detail.name"
      :subtitle="`${detail.country} · ICAO ${detail.icao_code ?? '—'}`"
    >
      <template #actions>
        <span class="badge badge-mono">{{ detail.iata_code }}</span>
        <RouterLink to="/airlines" class="btn btn-glass">
          <span class="btn-label"><AeroIcon name="chevron-left" :size="13" /> All airlines</span>
        </RouterLink>
      </template>
    </AeroPageHeader>

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-2 sm:max-w-[520px]">
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.route_count) }}</div>
          <div class="stat-label">Routes</div>
        </div>
        <span class="orb orb-aqua"><AeroIcon name="route" :size="17" /></span>
      </div>
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.airport_count) }}</div>
          <div class="stat-label">Airports</div>
        </div>
        <span class="orb orb-lime"><AeroIcon name="tower" :size="17" /></span>
      </div>
    </div>

    <AeroWindow class="mt-4" dense title="Filter routes" subtitle="Origin and destination are IATA codes">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <label class="block">
          <span class="field-label">Origin</span>
          <input v-model="filters.origin" class="field mono" placeholder="SYD" maxlength="3" />
        </label>
        <label class="block">
          <span class="field-label">Destination</span>
          <input v-model="filters.destination" class="field mono" placeholder="MEL" maxlength="3" />
        </label>
        <label class="col-span-2 block lg:col-span-1">
          <span class="field-label">Rows per page</span>
          <span class="select-wrap">
            <select v-model.number="pageSize" class="field" @change="page = 1">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select>
          </span>
        </label>
        <div class="col-span-2 flex items-end pb-1 lg:col-span-1">
          <button class="btn btn-sm btn-glass" @click="reset">
            <span class="btn-label"><AeroIcon name="refresh" :size="12" /> Clear filters</span>
          </button>
        </div>
      </div>
    </AeroWindow>

    <AeroWindow
      class="mt-4"
      dense
      title="Routes"
      :subtitle="`${total} records · page ${page} of ${pages}`"
    >
      <template #actions>
        <span class="badge"><AeroIcon name="check" :size="11" /> live</span>
      </template>

      <p
        v-if="error"
        class="mb-3 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
      >
        {{ error }}
      </p>

      <AeroTable
        :columns="columns"
        :rows="rows as unknown as Record<string, unknown>[]"
        row-key="route_id"
        :loading="loading"
      >
        <template #cell-route_id="{ value }">
          <span class="mono">#{{ value }}</span>
        </template>
        <template #cell-origin_iata="{ value }">
          <RouterLink :to="`/airports/${value}`" class="badge badge-mono">{{ value }}</RouterLink>
        </template>
        <template #cell-destination_iata="{ value }">
          <RouterLink :to="`/airports/${value}`" class="badge badge-mono">{{ value }}</RouterLink>
        </template>
        <template #cell-stops="{ value }">
          <span v-if="value === 0" class="badge badge-lime">Nonstop</span>
          <span v-else class="mono">{{ value }}</span>
        </template>
        <template #empty>
          <AeroEmpty
            icon="route"
            :title="filters.origin || filters.destination ? 'No matching routes' : 'No routes yet'"
            :text="
              filters.origin || filters.destination
                ? 'No routes from this airline match that origin and destination pair.'
                : 'This airline has no routes in the current dataset.'
            "
          >
            <button
              v-if="filters.origin || filters.destination"
              class="btn btn-sm btn-glass mt-2"
              @click="reset"
            >
              <span class="btn-label">Clear filters</span>
            </button>
          </AeroEmpty>
        </template>
      </AeroTable>

      <template #footer>
        <AeroPager
          :page="page"
          :pages="pages"
          :total="total"
          :page-size="pageSize"
          unit="routes"
          @update:page="(value) => (page = value)"
        />
      </template>
    </AeroWindow>
  </template>
</template>
