<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AeroDrawer from '@/components/AeroDrawer.vue'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Route, RouteExpanded } from '@/api/types'

type StopsFilter = 'any' | '0' | '1' | '2plus'
type CodeshareFilter = 'any' | 'Y' | 'N'

const filters = reactive({
  airline: '',
  origin: '',
  destination: '',
  maxStops: 'any' as StopsFilter,
  codeshare: 'any' as CodeshareFilter,
})
const page = ref(1)
const pageSize = ref(10)
const rows = ref<Record<string, unknown>[]>([])
const total = ref(0)
const pages = ref(1)
const loading = ref(true)
const error = ref('')

const drawerOpen = ref(false)
const detail = ref<RouteExpanded | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

// The API can only cap stops (`max_stops` = stops <= n), so the "2+" option is
// resolved by scanning the filtered result set once and paginating locally.
// The scan is cached per filter signature so paging does not re-request it.
const scanCache = new Map<string, Route[]>()

const columns: AeroColumn[] = [
  { key: 'route_id', label: 'Route ID', width: '92px', mono: true },
  { key: 'airline_iata', label: 'Airline', width: '110px' },
  { key: 'route_label', label: 'Route', width: '150px', mono: true },
  { key: 'stops_label', label: 'Stops' },
  { key: 'equipment', label: 'Equipment', width: '130px', mono: true },
  { key: 'codeshare_label', label: 'Codeshare', width: '110px' },
]

function stopsLabel(stops: number): string {
  if (stops === 0) return 'Direct'
  return `${stops} stop${stops === 1 ? '' : 's'}`
}

function toRows(items: Route[]): Record<string, unknown>[] {
  return items.map((route) => ({
    route_id: route.route_id,
    airline_iata: route.airline_iata,
    route_label: `${route.origin_iata} → ${route.destination_iata}`,
    stops_label: stopsLabel(route.stops),
    equipment: route.equipment ?? '—',
    codeshare_label: route.codeshare === 'Y' ? 'Yes' : 'No',
  }))
}

const queryKey = computed(() =>
  [
    filters.airline,
    filters.origin,
    filters.destination,
    filters.maxStops,
    filters.codeshare,
    page.value,
    pageSize.value,
  ].join('|'),
)

let timer: number | undefined

function baseQuery() {
  return {
    airline: filters.airline.trim().toUpperCase() || undefined,
    origin: filters.origin.trim().toUpperCase() || undefined,
    destination: filters.destination.trim().toUpperCase() || undefined,
    codeshare: filters.codeshare === 'any' ? undefined : filters.codeshare,
  }
}

async function scanStopsTwoPlus(): Promise<Route[]> {
  const key = [
    filters.airline.trim().toUpperCase(),
    filters.origin.trim().toUpperCase(),
    filters.destination.trim().toUpperCase(),
    filters.codeshare,
  ].join('|')
  const cached = scanCache.get(key)
  if (cached) return cached

  const collected: Route[] = []
  let current = 1
  let last = 1
  do {
    const result = await api.routes({ ...baseQuery(), page: current, page_size: 100 })
    collected.push(...result.items.filter((route) => route.stops >= 2))
    last = Math.max(1, result.pages)
    current += 1
  } while (current <= last)

  scanCache.set(key, collected)
  return collected
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    if (filters.maxStops === '2plus') {
      const items = await scanStopsTwoPlus()
      total.value = items.length
      pages.value = Math.max(1, Math.ceil(items.length / pageSize.value))
      if (page.value > pages.value) page.value = pages.value
      const start = (page.value - 1) * pageSize.value
      rows.value = toRows(items.slice(start, start + pageSize.value))
      return
    }

    const result = await api.routes({
      ...baseQuery(),
      max_stops: filters.maxStops === 'any' ? undefined : Number(filters.maxStops),
      page: page.value,
      page_size: pageSize.value,
    })
    total.value = result.total
    pages.value = Math.max(1, result.pages)
    if (page.value > pages.value) page.value = pages.value
    rows.value = toRows(result.items)
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load routes.'
    rows.value = []
    total.value = 0
    pages.value = 1
  } finally {
    loading.value = false
  }
}

watch(
  queryKey,
  () => {
    window.clearTimeout(timer)
    timer = window.setTimeout(load, 220)
  },
  { immediate: true },
)

watch(
  () => [filters.airline, filters.origin, filters.destination, filters.maxStops, filters.codeshare].join('|'),
  () => {
    if (page.value !== 1) page.value = 1
  },
)

onBeforeUnmount(() => window.clearTimeout(timer))

function reset(): void {
  filters.airline = ''
  filters.origin = ''
  filters.destination = ''
  filters.maxStops = 'any'
  filters.codeshare = 'any'
  page.value = 1
}

function onRowClick(row: Record<string, unknown>): void {
  void openDetail(Number(row.route_id))
}

async function openDetail(routeId: number): Promise<void> {
  drawerOpen.value = true
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    detail.value = (await api.route(routeId)) as unknown as RouteExpanded
  } catch (err) {
    detailError.value = err instanceof ApiError ? err.message : 'Could not load this route.'
  } finally {
    detailLoading.value = false
  }
}

const drawerTitle = computed(() => {
  if (!detail.value) return 'Route detail'
  return `${detail.value.origin_iata} → ${detail.value.destination_iata}`
})

const drawerSubtitle = computed(() => {
  if (!detail.value) return 'Loading route record'
  return `Route ${detail.value.route_id} · ${detail.value.airline_iata}`
})

const detailStops = computed(() => (detail.value ? stopsLabel(detail.value.stops) : '—'))
</script>

<template>
  <AeroPageHeader
    eyebrow="Network"
    title="Routes"
    subtitle="Browse the route network by airline, endpoints and stop count."
  >
    <template #actions>
      <button class="btn btn-glass" @click="reset">
        <span class="btn-label"><AeroIcon name="refresh" :size="13" /> Reset filters</span>
      </button>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Search" subtitle="Filters apply as you type">
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <label class="block">
        <span class="field-label">Airline (IATA)</span>
        <input v-model="filters.airline" class="field mono" placeholder="QF" maxlength="3" />
      </label>
      <label class="block">
        <span class="field-label">Origin (IATA)</span>
        <input v-model="filters.origin" class="field mono" placeholder="SYD" maxlength="3" />
      </label>
      <label class="block">
        <span class="field-label">Destination (IATA)</span>
        <input v-model="filters.destination" class="field mono" placeholder="MEL" maxlength="3" />
      </label>
      <label class="block">
        <span class="field-label">Max stops</span>
        <span class="select-wrap">
          <select v-model="filters.maxStops" class="field">
            <option value="any">Any</option>
            <option value="0">0 — direct</option>
            <option value="1">1 stop</option>
            <option value="2plus">2+ stops</option>
          </select>
        </span>
      </label>
      <label class="block">
        <span class="field-label">Codeshare</span>
        <span class="select-wrap">
          <select v-model="filters.codeshare" class="field">
            <option value="any">Any</option>
            <option value="Y">Yes</option>
            <option value="N">No</option>
          </select>
        </span>
      </label>
      <label class="block">
        <span class="field-label">Rows per page</span>
        <span class="select-wrap">
          <select v-model.number="pageSize" class="field">
            <option :value="10">10</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
          </select>
        </span>
      </label>
    </div>
    <p v-if="filters.maxStops === '2plus'" class="field-hint">
      “2+ stops” is evaluated over the full filtered set; the API has no minimum-stops filter.
    </p>
  </AeroWindow>

  <AeroWindow class="mt-4" dense title="Routes" :subtitle="`${total} routes · page ${page} of ${pages}`">
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
      :rows="rows"
      row-key="route_id"
      :loading="loading"
      clickable
      @row-click="onRowClick"
    >
      <template #cell-route_id="{ value }">
        <span class="mono">{{ value }}</span>
      </template>
      <template #cell-airline_iata="{ value }">
        <span class="badge badge-mono">{{ value }}</span>
      </template>
      <template #cell-route_label="{ value }">
        <span class="mono font-normal text-[#08354f]">{{ value }}</span>
      </template>
      <template #cell-stops_label="{ value }">
        <span class="font-light text-[#255b78]">{{ value }}</span>
      </template>
      <template #cell-codeshare_label="{ value }">
        <span class="font-light text-[#255b78]">{{ value }}</span>
      </template>
      <template #empty>
        <AeroEmpty
          title="No routes match"
          text="Try another airline, a different airport pair, or relax the stop and codeshare filters."
        >
          <button class="btn btn-sm btn-glass mt-2" @click="reset">
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

  <AeroDrawer v-model="drawerOpen" :title="drawerTitle" :subtitle="drawerSubtitle" width="460px">
    <div v-if="detailLoading" class="space-y-3">
      <span class="skeleton" style="width: 58%" />
      <span class="skeleton" style="width: 84%" />
      <span class="skeleton" style="width: 42%" />
      <span class="skeleton" style="width: 72%" />
    </div>

    <p v-else-if="detailError" class="rounded-[7px] border border-[rgba(255,150,140,0.45)] px-2.5 py-2 text-[12.5px] font-light text-[#ffb5ac]">
      {{ detailError }}
    </p>

    <div v-else-if="detail" class="space-y-4">
      <div class="flex flex-wrap items-center gap-2">
        <span class="badge badge-mono">{{ detail.airline_iata }}</span>
        <span class="badge badge-mono">{{ detail.origin_iata }} → {{ detail.destination_iata }}</span>
        <span class="badge">{{ detailStops }}</span>
      </div>

      <div>
        <div class="text-[10.5px] font-normal tracking-[0.16em] text-[rgba(220,242,255,0.6)] uppercase">
          Airline
        </div>
        <RouterLink
          :to="`/airlines/${detail.airline.iata_code}`"
          class="mt-1 inline-flex flex-wrap items-center gap-2 text-[15px] font-light text-[#eaf7ff] underline decoration-white/30 underline-offset-4 hover:decoration-white"
          @click="drawerOpen = false"
        >
          {{ detail.airline.name }}
          <span class="badge badge-mono">{{ detail.airline.iata_code }}</span>
        </RouterLink>
        <div class="text-[12px] font-light text-[rgba(220,242,255,0.65)]">{{ detail.airline.country }}</div>
      </div>

      <div class="grid gap-2.5 sm:grid-cols-2">
        <RouterLink
          :to="`/airports/${detail.origin_airport.iata_code}`"
          class="tile block"
          @click="drawerOpen = false"
        >
          <div class="text-[10.5px] font-normal tracking-[0.16em] text-[rgba(10,58,85,0.65)] uppercase">
            Origin
          </div>
          <div class="mono mt-1 text-[15px]">{{ detail.origin_airport.iata_code }}</div>
          <div class="mt-0.5 text-[13px] font-normal text-[#0a4260]">{{ detail.origin_airport.name }}</div>
          <div class="text-[12px] font-light text-[#2f6683]">
            {{ detail.origin_airport.city }}, {{ detail.origin_airport.country }}
          </div>
        </RouterLink>

        <RouterLink
          :to="`/airports/${detail.destination_airport.iata_code}`"
          class="tile block"
          @click="drawerOpen = false"
        >
          <div class="text-[10.5px] font-normal tracking-[0.16em] text-[rgba(10,58,85,0.65)] uppercase">
            Destination
          </div>
          <div class="mono mt-1 text-[15px]">{{ detail.destination_airport.iata_code }}</div>
          <div class="mt-0.5 text-[13px] font-normal text-[#0a4260]">{{ detail.destination_airport.name }}</div>
          <div class="text-[12px] font-light text-[#2f6683]">
            {{ detail.destination_airport.city }}, {{ detail.destination_airport.country }}
          </div>
        </RouterLink>
      </div>

      <dl class="grid grid-cols-3 gap-3 border-t border-white/20 pt-3">
        <div>
          <dt class="text-[10.5px] font-normal tracking-[0.14em] text-[rgba(220,242,255,0.6)] uppercase">
            Stops
          </dt>
          <dd class="mt-1 text-[15px] font-light text-[#eaf7ff]">{{ detailStops }}</dd>
        </div>
        <div>
          <dt class="text-[10.5px] font-normal tracking-[0.14em] text-[rgba(220,242,255,0.6)] uppercase">
            Equipment
          </dt>
          <dd class="mono mt-1 text-[13px] text-[#eaf7ff]">{{ detail.equipment ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-[10.5px] font-normal tracking-[0.14em] text-[rgba(220,242,255,0.6)] uppercase">
            Codeshare
          </dt>
          <dd class="mt-1 text-[15px] font-light text-[#eaf7ff]">
            {{ detail.codeshare === 'Y' ? 'Yes' : 'No' }}
          </dd>
        </div>
      </dl>

      <div class="flex flex-wrap gap-2 border-t border-white/20 pt-3">
        <RouterLink
          :to="`/airports/${detail.origin_airport.iata_code}`"
          class="btn btn-sm btn-glass"
          @click="drawerOpen = false"
        >
          <span class="btn-label"><AeroIcon name="tower" :size="12" /> Origin airport</span>
        </RouterLink>
        <RouterLink
          :to="`/airports/${detail.destination_airport.iata_code}`"
          class="btn btn-sm btn-glass"
          @click="drawerOpen = false"
        >
          <span class="btn-label"><AeroIcon name="tower" :size="12" /> Destination airport</span>
        </RouterLink>
      </div>
    </div>

    <template #footer>
      <button class="btn btn-sm btn-glass ml-auto" @click="drawerOpen = false">
        <span class="btn-label">Close</span>
      </button>
    </template>
  </AeroDrawer>
</template>
