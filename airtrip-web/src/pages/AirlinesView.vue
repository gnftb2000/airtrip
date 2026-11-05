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
import type { Airline } from '@/api/types'

const router = useRouter()

const filters = reactive({ q: '', country: '', iata_code: '', fuzzy: false })
const page = ref(1)
const pageSize = ref(10)
const rows = ref<Airline[]>([])
const total = ref(0)
const pages = ref(1)
const loading = ref(true)
const error = ref('')

const columns: AeroColumn[] = [
  { key: 'iata_code', label: 'IATA', width: '76px', mono: true },
  { key: 'icao_code', label: 'ICAO', width: '86px', mono: true },
  { key: 'name', label: 'Airline' },
  { key: 'country', label: 'Country', width: '180px' },
]

const queryKey = computed(() =>
  [filters.q, filters.country, filters.iata_code, filters.fuzzy, page.value, pageSize.value].join('|'),
)

let timer: number | undefined

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await api.airlines({
      q: filters.q.trim() || undefined,
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
    error.value = err instanceof ApiError ? err.message : 'Could not load airlines.'
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
  () => [filters.q, filters.country, filters.iata_code, filters.fuzzy].join('|'),
  () => {
    if (page.value !== 1) page.value = 1
  },
)

// The API rejects fuzzy ranking without a query term; keep the two in step.
watch(
  () => filters.q,
  (value) => {
    if (!value.trim()) filters.fuzzy = false
  },
)

watch(pageSize, () => {
  if (page.value !== 1) page.value = 1
})

onBeforeUnmount(() => window.clearTimeout(timer))

function reset(): void {
  filters.q = ''
  filters.country = ''
  filters.iata_code = ''
  filters.fuzzy = false
  page.value = 1
}

function open(code: string): void {
  router.push(`/airlines/${code}`)
}
</script>

<template>
  <AeroPageHeader
    eyebrow="Network"
    title="Airlines"
    subtitle="Every carrier in the dataset, from flag carriers to regional operators."
  >
    <template #actions>
      <button class="btn btn-glass" @click="reset">
        <span class="btn-label"><AeroIcon name="refresh" :size="13" /> Reset filters</span>
      </button>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Search" subtitle="Filters apply as you type">
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label class="block sm:col-span-2">
        <span class="field-label">Query</span>
        <input v-model="filters.q" class="field" placeholder="Qantas, Japan, QF…" />
      </label>
      <label class="block">
        <span class="field-label">Country</span>
        <input v-model="filters.country" class="field" placeholder="Australia" />
      </label>
      <label class="block">
        <span class="field-label">IATA code</span>
        <input v-model="filters.iata_code" class="field mono" placeholder="QF" maxlength="3" />
      </label>
      <div class="flex flex-col justify-end gap-1 pb-1">
        <label class="flex items-center gap-2">
          <input v-model="filters.fuzzy" type="checkbox" class="checkbox" :disabled="!filters.q.trim()" />
          <span class="text-[12.5px] font-light text-[color:var(--ink-soft)]">Fuzzy matching</span>
        </label>
        <span class="text-[11px] font-light text-[color:var(--ink-soft)]">Requires a query term</span>
      </div>
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
    title="Airlines"
    :subtitle="`${total} records · page ${page} of ${pages}`"
  >
    <template #actions>
      <span class="badge"><AeroIcon name="check" :size="11" /> live</span>
    </template>

    <p
      v-if="error"
      class="mb-3 rounded-[7px] border border-[var(--danger-border)] bg-[var(--danger-surface)] px-2.5 py-2 text-[12px] text-[color:var(--danger-ink)]"
    >
      {{ error }}
    </p>

    <AeroTable
      :columns="columns"
      :rows="rows as unknown as Record<string, unknown>[]"
      row-key="airline_id"
      :loading="loading"
      clickable
      @row-click="(row) => open(String(row.iata_code))"
    >
      <template #cell-iata_code="{ value }">
        <span class="badge badge-mono">{{ value }}</span>
      </template>
      <template #cell-name="{ value }">
        <span class="font-normal text-[color:var(--ink)]">{{ value }}</span>
      </template>
      <template #empty>
        <AeroEmpty
          title="No airlines match"
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
        unit="airlines"
        @update:page="(value) => (page = value)"
      />
    </template>
  </AeroWindow>
</template>
