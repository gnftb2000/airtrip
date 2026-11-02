<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Airport } from '@/api/types'

const router = useRouter()

const filters = reactive({ q: '', city: '', country: '', iata_code: '', fuzzy: false })
const page = ref(1)
const pageSize = ref(10)
const rows = ref<Airport[]>([])
const total = ref(0)
const pages = ref(1)
const loading = ref(true)
const error = ref('')

const columns: AeroColumn[] = [
  { key: 'iata_code', label: 'IATA', width: '72px', mono: true },
  { key: 'name', label: 'Airport' },
  { key: 'city', label: 'City', width: '160px' },
  { key: 'country', label: 'Country', width: '170px' },
  { key: 'icao_code', label: 'ICAO', width: '80px', mono: true },
  { key: 'altitude', label: 'Alt (ft)', width: '86px', align: 'right', mono: true },
  { key: 'airport_id', label: 'ID', width: '64px', align: 'right', mono: true },
]

const queryKey = computed(() =>
  [filters.q, filters.city, filters.country, filters.iata_code, filters.fuzzy, page.value, pageSize.value].join('|'),
)

let timer: number | undefined

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await api.airports({
      q: filters.q.trim() || undefined,
      city: filters.city.trim() || undefined,
      country: filters.country.trim() || undefined,
      iata_code: filters.iata_code.trim() || undefined,
      fuzzy: filters.fuzzy || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = result.items
    total.value = result.total
    pages.value = Math.max(1, result.pages)
    if (page.value > pages.value) page.value = pages.value
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load airports.'
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
  () => [filters.q, filters.city, filters.country, filters.iata_code, filters.fuzzy].join('|'),
  () => {
    if (page.value !== 1) page.value = 1
  },
)

onBeforeUnmount(() => window.clearTimeout(timer))

function reset(): void {
  filters.q = ''
  filters.city = ''
  filters.country = ''
  filters.iata_code = ''
  filters.fuzzy = false
  page.value = 1
}

function open(code: string): void {
  router.push(`/airports/${code}`)
}
</script>

<template>
  <AeroPageHeader
    eyebrow="Network"
    title="Airports"
    subtitle="Every airport in the dataset, with the hub data behind each one."
  >
    <template #actions>
      <button class="btn btn-glass" @click="reset">
        <span class="btn-label"><AeroIcon name="refresh" :size="13" /> Reset filters</span>
      </button>
      <RouterLink to="/import" class="btn">
        <span class="btn-label"><AeroIcon name="upload" :size="13" /> Import dataset</span>
      </RouterLink>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Search" subtitle="Filters apply as you type">
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label class="block sm:col-span-2">
        <span class="field-label">Query</span>
        <input v-model="filters.q" class="field" placeholder="Sydney, Kingsford, SYD…" />
      </label>
      <label class="block">
        <span class="field-label">City</span>
        <input v-model="filters.city" class="field" placeholder="Sydney" />
      </label>
      <label class="block">
        <span class="field-label">Country</span>
        <input v-model="filters.country" class="field" placeholder="Australia" />
      </label>
      <label class="block">
        <span class="field-label">IATA code</span>
        <input v-model="filters.iata_code" class="field mono" placeholder="SYD" maxlength="3" />
      </label>
      <label class="flex items-end gap-2 pb-1">
        <input v-model="filters.fuzzy" type="checkbox" class="checkbox" />
        <span class="text-[12.5px] font-light text-[#255b78]">Fuzzy matching</span>
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
  </AeroWindow>

  <AeroWindow
    class="mt-4"
    dense
    title="Airports"
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
      row-key="airport_id"
      :loading="loading"
      clickable
      @row-click="(row) => open(String(row.iata_code))"
    >
      <template #cell-iata_code="{ value }">
        <span class="badge badge-mono">{{ value }}</span>
      </template>
      <template #cell-name="{ value }">
        <span class="font-normal text-[#08354f]">{{ value }}</span>
      </template>
      <template #empty>
        <AeroEmpty
          title="No airports match"
          text="Try a broader query, clear the filters, or import a fresh dataset."
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
        unit="airports"
        @update:page="(value) => (page = value)"
      />
    </template>
  </AeroWindow>
</template>
