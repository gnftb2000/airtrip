<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Airport, ImportStatus } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

interface Counts {
  airports: number
  airlines: number
  routes: number
}

interface Tile {
  label: string
  value: number | undefined
  loading: boolean
  icon: string
  tone: string
  to: string
}

const counts = ref<Counts | null>(null)
const countsLoading = ref(true)
const countsError = ref('')
const importState = ref<ImportStatus | null>(null)

const planTotal = ref<number | null>(null)
const plansLoading = ref(true)
const plansError = ref('')

const recent = ref<Airport[]>([])
const recentLoading = ref(true)
const recentError = ref('')

const subtitle = computed(() =>
  auth.account
    ? `Welcome back, ${auth.account.username}. Here is the network at a glance.`
    : 'Here is the network at a glance.',
)

const refreshing = computed(
  () => countsLoading.value || plansLoading.value || recentLoading.value,
)

const tiles = computed<Tile[]>(() => [
  {
    label: 'Airports',
    value: counts.value?.airports,
    loading: countsLoading.value,
    icon: 'tower',
    tone: '',
    to: '/airports',
  },
  {
    label: 'Airlines',
    value: counts.value?.airlines,
    loading: countsLoading.value,
    icon: 'globe',
    tone: 'orb-aqua',
    to: '/airlines',
  },
  {
    label: 'Routes',
    value: counts.value?.routes,
    loading: countsLoading.value,
    icon: 'route',
    tone: 'orb-lime',
    to: '/routes',
  },
  {
    label: 'My plans',
    value: planTotal.value ?? undefined,
    loading: plansLoading.value,
    icon: 'plan',
    tone: '',
    to: '/plans',
  },
])

const datasetEmpty = computed(() => {
  const value = counts.value
  return Boolean(value && value.airports === 0 && value.airlines === 0 && value.routes === 0)
})

const lastImport = computed(() => importState.value?.last_import ?? null)

const recentColumns: AeroColumn[] = [
  { key: 'iata_code', label: 'IATA', width: '72px', mono: true },
  { key: 'name', label: 'Airport' },
  { key: 'city', label: 'City', width: '150px' },
  { key: 'country', label: 'Country', width: '150px' },
]

const whenFormatter = new Intl.DateTimeFormat('en-AU', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatWhen(value: string | null | undefined): string {
  if (!value) return 'Never'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : whenFormatter.format(date)
}

async function loadCounts(): Promise<void> {
  countsLoading.value = true
  countsError.value = ''
  try {
    if (auth.isAdmin) {
      // The import status endpoint carries the authoritative dataset sizes.
      const status = await api.importStatus()
      importState.value = status
      counts.value = status.counts
    } else {
      // /api/import/status is admin only, so members read the page totals instead.
      const [airports, airlines, routes] = await Promise.all([
        api.airports({ page: 1, page_size: 1 }),
        api.airlines({ page: 1, page_size: 1 }),
        api.routes({ page: 1, page_size: 1 }),
      ])
      importState.value = null
      counts.value = {
        airports: airports.total,
        airlines: airlines.total,
        routes: routes.total,
      }
    }
  } catch (err) {
    countsError.value =
      err instanceof ApiError ? err.message : 'Could not load the network counts.'
    counts.value = null
  } finally {
    countsLoading.value = false
  }
}

async function loadPlans(): Promise<void> {
  plansLoading.value = true
  plansError.value = ''
  try {
    const result = await api.plans({ page: 1, page_size: 1 })
    planTotal.value = result.total
  } catch (err) {
    plansError.value =
      err instanceof ApiError ? err.message : 'Could not load your travel plans.'
    planTotal.value = null
  } finally {
    plansLoading.value = false
  }
}

async function loadRecent(): Promise<void> {
  recentLoading.value = true
  recentError.value = ''
  try {
    const result = await api.airports({ page: 1, page_size: 5 })
    recent.value = result.items
  } catch (err) {
    recentError.value =
      err instanceof ApiError ? err.message : 'Could not load the latest airports.'
    recent.value = []
  } finally {
    recentLoading.value = false
  }
}

async function refresh(): Promise<void> {
  await Promise.all([loadCounts(), loadPlans(), loadRecent()])
}

function openAirport(code: string): void {
  void router.push(`/airports/${code}`)
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <AeroPageHeader eyebrow="Overview" title="Dashboard" :subtitle="subtitle">
    <template #actions>
      <button class="btn btn-sm btn-glass" :disabled="refreshing" @click="refresh">
        <span class="btn-label">
          <AeroIcon name="refresh" :size="13" /> {{ refreshing ? 'Refreshing…' : 'Refresh' }}
        </span>
      </button>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Network at a glance" subtitle="Live counts from the AirTrip dataset">
    <template #actions>
      <span class="badge"><AeroIcon name="check" :size="11" /> live</span>
    </template>

    <p
      v-if="countsError"
      class="mb-3 flex flex-wrap items-center gap-2 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
    >
      <span>{{ countsError }}</span>
      <button class="btn btn-sm btn-glass ml-auto" @click="loadCounts">
        <span class="btn-label">Retry</span>
      </button>
    </p>

    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <RouterLink
        v-for="tile in tiles"
        :key="tile.label"
        :to="tile.to"
        class="tile flex items-center gap-3 transition-transform hover:-translate-y-0.5"
      >
        <div class="orb shrink-0" :class="tile.tone" style="width: 34px; height: 34px">
          <AeroIcon :name="tile.icon" :size="17" />
        </div>
        <div class="min-w-0">
          <div class="stat-value">
            <span v-if="tile.loading" class="skeleton" style="width: 52px; height: 24px" />
            <template v-else>{{ tile.value ?? '—' }}</template>
          </div>
          <div class="stat-label truncate">{{ tile.label }}</div>
        </div>
      </RouterLink>
    </div>

    <p
      v-if="!countsLoading && !countsError && datasetEmpty"
      class="mt-3 text-[12.5px] leading-relaxed font-light text-[#2a5f7d]"
    >
      The dataset is empty.
      <template v-if="auth.isAdmin">
        <RouterLink
          to="/import"
          class="font-normal text-[#0b5a86] underline decoration-[#0b5a86]/40 underline-offset-2"
        >
          Import the CSV datasets
        </RouterLink>
        to populate the network.
      </template>
      <template v-else> Ask an administrator to import the CSV datasets.</template>
    </p>
    <p v-if="plansError" class="mt-2 text-[11.5px] font-light text-[#983328]">{{ plansError }}</p>
  </AeroWindow>

  <div class="mt-4 grid gap-4 sm:grid-cols-2">
    <RouterLink to="/routes" class="win block transition-transform hover:-translate-y-0.5">
      <div class="win-body flex items-start gap-3.5">
        <div class="orb sweep shrink-0" style="width: 42px; height: 42px">
          <AeroIcon name="route" :size="20" />
        </div>
        <div class="min-w-0">
          <div class="text-[14.5px] font-normal text-[#0a4260]">Browse routes</div>
          <p class="mt-1 text-[12.5px] leading-relaxed font-light text-[#2a5f7d]">
            Search every connection by airline, origin and destination, then open a route for the
            full details.
          </p>
        </div>
        <span class="ml-auto shrink-0 text-[#2f6f92]">
          <AeroIcon name="chevron-right" :size="16" />
        </span>
      </div>
    </RouterLink>

    <RouterLink to="/plans/new" class="win block transition-transform hover:-translate-y-0.5">
      <div class="win-body flex items-start gap-3.5">
        <div class="orb orb-aqua sweep shrink-0" style="width: 42px; height: 42px">
          <AeroIcon name="plan" :size="20" />
        </div>
        <div class="min-w-0">
          <div class="text-[14.5px] font-normal text-[#0a4260]">Plan a trip</div>
          <p class="mt-1 text-[12.5px] leading-relaxed font-light text-[#2a5f7d]">
            Give your journey a name and dates, then collect the routes you want to fly and keep
            them on your account.
          </p>
        </div>
        <span class="ml-auto shrink-0 text-[#2f6f92]">
          <AeroIcon name="chevron-right" :size="16" />
        </span>
      </div>
    </RouterLink>
  </div>

  <div class="mt-4 grid items-start gap-4 lg:grid-cols-3">
    <div :class="auth.isAdmin ? 'lg:col-span-2' : 'lg:col-span-3'">
      <AeroWindow dense title="Recently added airports" subtitle="The five newest records in the dataset">
        <template #actions>
          <RouterLink to="/airports" class="btn btn-sm btn-glass">
            <span class="btn-label">All airports <AeroIcon name="chevron-right" :size="12" /></span>
          </RouterLink>
        </template>

        <p
          v-if="recentError"
          class="mb-3 flex flex-wrap items-center gap-2 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
        >
          <span>{{ recentError }}</span>
          <button class="btn btn-sm btn-glass ml-auto" @click="loadRecent">
            <span class="btn-label">Retry</span>
          </button>
        </p>

        <AeroTable
          :columns="recentColumns"
          :rows="recent as unknown as Record<string, unknown>[]"
          row-key="airport_id"
          :loading="recentLoading"
          :skeleton-rows="3"
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
              icon="tower"
              title="No airports yet"
              text="The dataset is empty. An administrator can import the CSV datasets to populate the network."
            >
              <RouterLink v-if="auth.isAdmin" to="/import" class="btn btn-sm btn-glass mt-2">
                <span class="btn-label">
                  <AeroIcon name="upload" :size="12" /> Import datasets
                </span>
              </RouterLink>
            </AeroEmpty>
          </template>
        </AeroTable>
      </AeroWindow>
    </div>

    <AeroWindow
      v-if="auth.isAdmin"
      dense
      title="Dataset import"
      subtitle="Latest upload on this server"
    >
      <div v-if="countsLoading" class="space-y-2.5">
        <span class="skeleton block" style="width: 45%; height: 10px" />
        <span class="skeleton block" style="width: 72%; height: 13px" />
        <span class="skeleton block" style="width: 58%; height: 10px" />
      </div>
      <p v-else-if="countsError" class="text-[12px] leading-relaxed font-light text-[#983328]">
        Status unavailable. Use Retry above to try again.
      </p>
      <template v-else>
        <div class="field-label">Last import</div>
        <div class="text-[13.5px] font-normal text-[#0a4260]">
          {{ formatWhen(importState?.last_import_at) }}
        </div>

        <div
          v-if="lastImport && (lastImport.replaced?.length || lastImport.imported)"
          class="mt-2.5 flex flex-wrap gap-1.5"
        >
          <span v-for="name in lastImport.replaced ?? []" :key="name" class="badge">
            {{ name }} replaced
          </span>
          <span
            v-for="(value, key) in lastImport.imported ?? {}"
            :key="key"
            class="badge badge-mono"
          >
            {{ key }} {{ value }}
          </span>
        </div>
        <p v-else class="mt-2 text-[12px] leading-relaxed font-light text-[#2a5f7d]">
          No import has run since the API process started. Replace datasets from the import page
          when you are ready.
        </p>

        <RouterLink to="/import" class="btn btn-sm mt-3">
          <span class="btn-label"><AeroIcon name="upload" :size="12" /> Open import</span>
        </RouterLink>
      </template>
    </AeroWindow>
  </div>
</template>
