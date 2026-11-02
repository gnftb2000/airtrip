<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Airline, Airport, AirportDetail, Route } from '@/api/types'

type TabId = 'routes' | 'airlines' | 'destinations'
type Direction = 'both' | 'departure' | 'arrival'

const route = useRoute()
const router = useRouter()
const iata = computed(() => String(route.params.iata ?? '').toUpperCase())

const detail = ref<AirportDetail | null>(null)
const detailLoading = ref(true)
const detailError = ref('')

const tab = ref<TabId>('routes')
const tabs: { id: TabId; label: string; icon: string }[] = [
  { id: 'routes', label: 'Routes', icon: 'route' },
  { id: 'airlines', label: 'Airlines', icon: 'plane' },
  { id: 'destinations', label: 'Destinations', icon: 'globe' },
]

const direction = ref<Direction>('both')
const directions: { id: Direction; label: string }[] = [
  { id: 'both', label: 'All' },
  { id: 'departure', label: 'Departures' },
  { id: 'arrival', label: 'Arrivals' },
]

const routesPage = ref(1)
const routesPageSize = ref(10)
const routes = ref<Route[]>([])
const routesTotal = ref(0)
const routesPages = ref(1)
const routesLoading = ref(false)
const routesError = ref('')

const airlinesPage = ref(1)
const airlinesPageSize = ref(10)
const airlines = ref<Airline[]>([])
const airlinesTotal = ref(0)
const airlinesPages = ref(1)
const airlinesLoading = ref(false)
const airlinesError = ref('')

const destinationsPage = ref(1)
const destinationsPageSize = ref(10)
const destinations = ref<Airport[]>([])
const destinationsTotal = ref(0)
const destinationsPages = ref(1)
const destinationsLoading = ref(false)
const destinationsError = ref('')

const airlineColumns: AeroColumn[] = [
  { key: 'iata_code', label: 'IATA', width: '76px', mono: true },
  { key: 'name', label: 'Airline' },
  { key: 'country', label: 'Country', width: '170px' },
  { key: 'icao_code', label: 'ICAO', width: '86px', mono: true },
]

const destinationColumns: AeroColumn[] = [
  { key: 'iata_code', label: 'IATA', width: '76px', mono: true },
  { key: 'name', label: 'Airport' },
  { key: 'city', label: 'City', width: '150px' },
  { key: 'country', label: 'Country', width: '160px' },
]

const routeColumns = computed<AeroColumn[]>(() => {
  const cols: AeroColumn[] = [{ key: 'airline_iata', label: 'Airline', width: '110px' }]
  if (direction.value !== 'departure') cols.push({ key: 'origin_iata', label: 'Origin', width: '100px' })
  if (direction.value !== 'arrival') cols.push({ key: 'destination_iata', label: 'Destination', width: '116px' })
  cols.push(
    { key: 'stops', label: 'Stops', width: '94px' },
    { key: 'equipment', label: 'Equipment', width: '116px', mono: true },
    { key: 'codeshare', label: 'Codeshare', width: '104px' },
  )
  return cols
})

const routesKey = computed(() =>
  [direction.value, routesPage.value, routesPageSize.value].join('|'),
)
const airlinesKey = computed(() => [airlinesPage.value, airlinesPageSize.value].join('|'))
const destinationsKey = computed(() =>
  [destinationsPage.value, destinationsPageSize.value].join('|'),
)

let routesSeq = 0
let airlinesSeq = 0
let destinationsSeq = 0

async function loadDetail(): Promise<void> {
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    detail.value = await api.airport(iata.value)
  } catch (err) {
    detailError.value = err instanceof ApiError ? err.message : 'Could not load this airport.'
  } finally {
    detailLoading.value = false
  }
}

async function loadRoutes(): Promise<void> {
  if (!detail.value) return
  const seq = ++routesSeq
  routesLoading.value = true
  routesError.value = ''
  try {
    const result = await api.airportRoutes(iata.value, {
      direction: direction.value,
      page: routesPage.value,
      page_size: routesPageSize.value,
    })
    if (seq !== routesSeq) return
    routes.value = result.items
    routesTotal.value = result.total
    routesPages.value = Math.max(1, result.pages)
    if (routesPage.value > routesPages.value) routesPage.value = routesPages.value
  } catch (err) {
    if (seq !== routesSeq) return
    routesError.value = err instanceof ApiError ? err.message : 'Could not load routes.'
    routes.value = []
    routesTotal.value = 0
    routesPages.value = 1
  } finally {
    if (seq === routesSeq) routesLoading.value = false
  }
}

async function loadAirlines(): Promise<void> {
  if (!detail.value) return
  const seq = ++airlinesSeq
  airlinesLoading.value = true
  airlinesError.value = ''
  try {
    const result = await api.airportAirlines(iata.value, {
      page: airlinesPage.value,
      page_size: airlinesPageSize.value,
    })
    if (seq !== airlinesSeq) return
    airlines.value = result.items
    airlinesTotal.value = result.total
    airlinesPages.value = Math.max(1, result.pages)
    if (airlinesPage.value > airlinesPages.value) airlinesPage.value = airlinesPages.value
  } catch (err) {
    if (seq !== airlinesSeq) return
    airlinesError.value = err instanceof ApiError ? err.message : 'Could not load airlines.'
    airlines.value = []
    airlinesTotal.value = 0
    airlinesPages.value = 1
  } finally {
    if (seq === airlinesSeq) airlinesLoading.value = false
  }
}

async function loadDestinations(): Promise<void> {
  if (!detail.value) return
  const seq = ++destinationsSeq
  destinationsLoading.value = true
  destinationsError.value = ''
  try {
    const result = await api.airportDestinations(iata.value, {
      page: destinationsPage.value,
      page_size: destinationsPageSize.value,
    })
    if (seq !== destinationsSeq) return
    destinations.value = result.items
    destinationsTotal.value = result.total
    destinationsPages.value = Math.max(1, result.pages)
    if (destinationsPage.value > destinationsPages.value) destinationsPage.value = destinationsPages.value
  } catch (err) {
    if (seq !== destinationsSeq) return
    destinationsError.value = err instanceof ApiError ? err.message : 'Could not load destinations.'
    destinations.value = []
    destinationsTotal.value = 0
    destinationsPages.value = 1
  } finally {
    if (seq === destinationsSeq) destinationsLoading.value = false
  }
}

function loadActiveTab(): void {
  if (tab.value === 'routes') void loadRoutes()
  else if (tab.value === 'airlines') void loadAirlines()
  else void loadDestinations()
}

watch(
  iata,
  () => {
    routesPage.value = 1
    airlinesPage.value = 1
    destinationsPage.value = 1
    direction.value = 'both'
    tab.value = 'routes'
    routesSeq += 1
    airlinesSeq += 1
    destinationsSeq += 1
    routes.value = []
    airlines.value = []
    destinations.value = []
    routesTotal.value = 0
    airlinesTotal.value = 0
    destinationsTotal.value = 0
    routesPages.value = 1
    airlinesPages.value = 1
    destinationsPages.value = 1
    routesLoading.value = false
    airlinesLoading.value = false
    destinationsLoading.value = false
    void loadDetail()
  },
  { immediate: true },
)

watch(detail, (value) => {
  if (value) loadActiveTab()
})

watch([routesKey, tab], () => {
  if (tab.value === 'routes' && detail.value) void loadRoutes()
})

watch([airlinesKey, tab], () => {
  if (tab.value === 'airlines' && detail.value) void loadAirlines()
})

watch([destinationsKey, tab], () => {
  if (tab.value === 'destinations' && detail.value) void loadDestinations()
})

function setDirection(value: Direction): void {
  if (direction.value === value) return
  direction.value = value
  if (routesPage.value !== 1) routesPage.value = 1
}

function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}

function openAirport(code: string): void {
  router.push(`/airports/${code}`)
}

function openAirline(code: string): void {
  router.push(`/airlines/${code}`)
}
</script>

<template>
  <div v-if="detailLoading && !detail" class="grid gap-4">
    <div class="tile h-[92px] animate-pulse" />
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div v-for="n in 4" :key="n" class="tile h-[86px] animate-pulse" />
    </div>
  </div>

  <template v-else-if="detailError && !detail">
    <AeroWindow title="Airport unavailable">
      <AeroEmpty :title="`Could not load ${iata}`" :text="detailError">
        <div class="mt-2 flex flex-wrap justify-center gap-2">
          <button class="btn btn-sm" @click="loadDetail">
            <span class="btn-label"><AeroIcon name="refresh" :size="12" /> Retry</span>
          </button>
          <RouterLink to="/airports" class="btn btn-sm btn-glass">
            <span class="btn-label"><AeroIcon name="chevron-left" :size="12" /> All airports</span>
          </RouterLink>
        </div>
      </AeroEmpty>
    </AeroWindow>
  </template>

  <template v-else-if="detail">
    <AeroPageHeader
      eyebrow="Airport"
      :title="detail.name"
      :subtitle="`${detail.city}, ${detail.country} · ICAO ${detail.icao_code ?? '—'}`"
    >
      <template #actions>
        <span class="badge badge-mono">{{ detail.iata_code }}</span>
        <RouterLink to="/airports" class="btn btn-glass">
          <span class="btn-label"><AeroIcon name="chevron-left" :size="13" /> All airports</span>
        </RouterLink>
      </template>
    </AeroPageHeader>

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.route_count) }}</div>
          <div class="stat-label">Routes</div>
        </div>
        <span class="orb orb-aqua"><AeroIcon name="route" :size="17" /></span>
      </div>
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.departure_route_count) }}</div>
          <div class="stat-label">Departures</div>
        </div>
        <span class="orb"><AeroIcon name="plane" :size="17" /></span>
      </div>
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.arrival_route_count) }}</div>
          <div class="stat-label">Arrivals</div>
        </div>
        <span class="orb orb-lime"><AeroIcon name="plane" :size="17" /></span>
      </div>
      <div class="tile flex items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="stat-value">{{ formatCount(detail.airline_count) }}</div>
          <div class="stat-label">Airlines</div>
        </div>
        <span class="orb orb-aqua"><AeroIcon name="users" :size="17" /></span>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap items-center gap-2" role="tablist" aria-label="Airport sections">
      <button
        v-for="item in tabs"
        :key="item.id"
        type="button"
        role="tab"
        class="btn btn-sm"
        :class="tab === item.id ? '' : 'btn-glass'"
        :aria-selected="tab === item.id"
        @click="tab = item.id"
      >
        <span class="btn-label"><AeroIcon :name="item.icon" :size="12" /> {{ item.label }}</span>
      </button>
    </div>

    <AeroWindow
      v-if="tab === 'routes'"
      class="mt-4"
      dense
      title="Routes"
      :subtitle="`${routesTotal} records · page ${routesPage} of ${routesPages}`"
    >
      <template #actions>
        <label class="flex items-center gap-2">
          <span class="hidden text-[11px] font-light tracking-[0.4px] text-[#2f6683] uppercase sm:inline">Rows</span>
          <span class="select-wrap w-[72px]">
            <select v-model.number="routesPageSize" class="field !h-[28px] !px-2.5 !text-[12px]" @change="routesPage = 1">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select>
          </span>
        </label>
      </template>

      <div class="mb-3">
        <span class="field-label">Direction</span>
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="item in directions"
            :key="item.id"
            type="button"
            class="btn btn-sm"
            :class="direction === item.id ? '' : 'btn-glass'"
            :aria-pressed="direction === item.id"
            @click="setDirection(item.id)"
          >
            <span class="btn-label">{{ item.label }}</span>
          </button>
        </div>
      </div>

      <p
        v-if="routesError"
        class="mb-3 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
      >
        {{ routesError }}
      </p>

      <AeroTable
        :columns="routeColumns"
        :rows="routes as unknown as Record<string, unknown>[]"
        row-key="route_id"
        :loading="routesLoading"
      >
        <template #cell-airline_iata="{ value }">
          <RouterLink :to="`/airlines/${value}`" class="badge badge-mono">{{ value }}</RouterLink>
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
        <template #cell-codeshare="{ value }">
          <span v-if="value === 'Y'" class="badge badge-aqua">Yes</span>
          <span v-else-if="value === 'N'" class="text-[12px] font-light text-[#255b78]">No</span>
          <span v-else class="text-[12px] font-light text-[#255b78]">—</span>
        </template>
        <template #empty>
          <AeroEmpty
            icon="route"
            title="No routes to show"
            :text="
              direction === 'both'
                ? 'This airport has no routes in the current dataset.'
                : direction === 'departure'
                  ? 'This airport has no departing routes in the current dataset.'
                  : 'This airport has no arriving routes in the current dataset.'
            "
          />
        </template>
      </AeroTable>

      <template #footer>
        <AeroPager
          :page="routesPage"
          :pages="routesPages"
          :total="routesTotal"
          :page-size="routesPageSize"
          unit="routes"
          @update:page="(value) => (routesPage = value)"
        />
      </template>
    </AeroWindow>

    <AeroWindow
      v-else-if="tab === 'airlines'"
      class="mt-4"
      dense
      title="Airlines"
      :subtitle="`${airlinesTotal} records · page ${airlinesPage} of ${airlinesPages}`"
    >
      <template #actions>
        <label class="flex items-center gap-2">
          <span class="hidden text-[11px] font-light tracking-[0.4px] text-[#2f6683] uppercase sm:inline">Rows</span>
          <span class="select-wrap w-[72px]">
            <select v-model.number="airlinesPageSize" class="field !h-[28px] !px-2.5 !text-[12px]" @change="airlinesPage = 1">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select>
          </span>
        </label>
      </template>

      <p
        v-if="airlinesError"
        class="mb-3 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
      >
        {{ airlinesError }}
      </p>

      <AeroTable
        :columns="airlineColumns"
        :rows="airlines as unknown as Record<string, unknown>[]"
        row-key="airline_id"
        :loading="airlinesLoading"
        clickable
        @row-click="(row) => openAirline(String(row.iata_code))"
      >
        <template #cell-iata_code="{ value }">
          <span class="badge badge-mono">{{ value }}</span>
        </template>
        <template #cell-name="{ value }">
          <span class="font-normal text-[#08354f]">{{ value }}</span>
        </template>
        <template #empty>
          <AeroEmpty
            icon="plane"
            title="No airlines serve this airport"
            text="No carrier is linked to this airport in the current dataset."
          />
        </template>
      </AeroTable>

      <template #footer>
        <AeroPager
          :page="airlinesPage"
          :pages="airlinesPages"
          :total="airlinesTotal"
          :page-size="airlinesPageSize"
          unit="airlines"
          @update:page="(value) => (airlinesPage = value)"
        />
      </template>
    </AeroWindow>

    <AeroWindow
      v-else
      class="mt-4"
      dense
      title="Destinations"
      :subtitle="`${destinationsTotal} records · page ${destinationsPage} of ${destinationsPages}`"
    >
      <template #actions>
        <label class="flex items-center gap-2">
          <span class="hidden text-[11px] font-light tracking-[0.4px] text-[#2f6683] uppercase sm:inline">Rows</span>
          <span class="select-wrap w-[72px]">
            <select v-model.number="destinationsPageSize" class="field !h-[28px] !px-2.5 !text-[12px]" @change="destinationsPage = 1">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
            </select>
          </span>
        </label>
      </template>

      <p
        v-if="destinationsError"
        class="mb-3 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
      >
        {{ destinationsError }}
      </p>

      <AeroTable
        :columns="destinationColumns"
        :rows="destinations as unknown as Record<string, unknown>[]"
        row-key="airport_id"
        :loading="destinationsLoading"
        clickable
        @row-click="(row) => openAirport(String(row.iata_code))"
      >
        <template #cell-iata_code="{ value }">
          <span class="badge badge-mono">{{ value }}</span>
        </template>
        <template #cell-name="{ value }">
          <span class="font-normal text-[#08354f]">{{ value }}</span>
        </template>
        <template #empty>
          <AeroEmpty
            icon="globe"
            title="No destinations yet"
            text="This airport has no onward destinations in the current dataset."
          />
        </template>
      </AeroTable>

      <template #footer>
        <AeroPager
          :page="destinationsPage"
          :pages="destinationsPages"
          :total="destinationsTotal"
          :page-size="destinationsPageSize"
          unit="destinations"
          @update:page="(value) => (destinationsPage = value)"
        />
      </template>
    </AeroWindow>
  </template>
</template>
