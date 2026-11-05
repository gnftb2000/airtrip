<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { ImportResult, ImportStatus } from '@/api/types'
import { useToastStore } from '@/stores/toast'

type DatasetKey = 'airports' | 'airlines' | 'routes'

interface DatasetMeta {
  key: DatasetKey
  file: string
  hint: string
}

interface ImportDetail {
  dataset?: string
  field?: string
  issue?: string
  row?: number
  route_id?: number
}

const datasets: DatasetMeta[] = [
  {
    key: 'airports',
    file: 'airports.csv',
    hint: 'airport_id, name, city, country, iata_code, icao_code, latitude, longitude, altitude, timezone',
  },
  {
    key: 'airlines',
    file: 'airlines.csv',
    hint: 'airline_id, name, iata_code, icao_code, country',
  },
  {
    key: 'routes',
    file: 'routes.csv',
    hint: 'route_id, airline_id, airline_iata, origin_airport_id, origin_iata, destination_airport_id, destination_iata, codeshare, stops, equipment',
  },
]

const toast = useToastStore()

const status = ref<ImportStatus | null>(null)
const statusLoading = ref(true)
const statusError = ref('')

const files = reactive<Record<DatasetKey, File | null>>({
  airports: null,
  airlines: null,
  routes: null,
})
const fileErrors = reactive<Record<DatasetKey, string>>({
  airports: '',
  airlines: '',
  routes: '',
})
const fileVersions = reactive<Record<DatasetKey, number>>({
  airports: 0,
  airlines: 0,
  routes: 0,
})

const busy = ref(false)
const result = ref<ImportResult | null>(null)
const errorMessage = ref('')
const errorDetails = ref<ImportDetail[]>([])

const counts = computed(() => status.value?.counts ?? null)
const lastImport = computed(() => status.value?.last_import ?? null)
const datasetEmpty = computed(() => {
  const value = counts.value
  return Boolean(value && value.airports === 0 && value.airlines === 0 && value.routes === 0)
})

const statusTiles = computed(() => [
  { label: 'Airports', value: counts.value?.airports },
  { label: 'Airlines', value: counts.value?.airlines },
  { label: 'Routes', value: counts.value?.routes },
])

const selected = computed<DatasetKey[]>(() =>
  datasets.filter((dataset) => files[dataset.key] !== null).map((dataset) => dataset.key),
)

const hasFileError = computed(() => datasets.some((dataset) => fileErrors[dataset.key] !== ''))

const canSubmit = computed(
  () => selected.value.length > 0 && !busy.value && !hasFileError.value,
)

const whenFormatter = new Intl.DateTimeFormat('en-AU', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatWhen(value: string | null | undefined): string {
  if (!value) return 'Never'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : whenFormatter.format(date)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function extractDetails(err: ApiError): ImportDetail[] {
  const body = err.body as unknown as { details?: unknown } | undefined
  if (!body || !Array.isArray(body.details)) return []
  return body.details.filter(
    (item): item is ImportDetail => typeof item === 'object' && item !== null,
  )
}

async function loadStatus(): Promise<void> {
  statusLoading.value = true
  statusError.value = ''
  try {
    status.value = await api.importStatus()
  } catch (err) {
    statusError.value =
      err instanceof ApiError ? err.message : 'Could not load the import status.'
    status.value = null
  } finally {
    statusLoading.value = false
  }
}

function onFileChange(key: DatasetKey, event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  fileErrors[key] = ''

  if (file && !/\.csv$/i.test(file.name)) {
    fileErrors[key] = 'Only .csv files are accepted.'
    files[key] = null
    input.value = ''
    return
  }

  files[key] = file
}

function clearFile(key: DatasetKey): void {
  files[key] = null
  fileErrors[key] = ''
  fileVersions[key] += 1
}

async function submit(): Promise<void> {
  errorMessage.value = ''
  errorDetails.value = []
  result.value = null

  if (hasFileError.value) {
    errorMessage.value = 'Fix the file selection before importing.'
    return
  }
  if (selected.value.length === 0) {
    errorMessage.value = 'Choose at least one CSV file to import.'
    return
  }

  const payload: { airports?: File; airlines?: File; routes?: File } = {}
  for (const key of selected.value) {
    const file = files[key]
    if (file) payload[key] = file
  }

  busy.value = true
  try {
    const response = await api.uploadDatasets(payload)
    result.value = response
    toast.ok(response.message || 'The import completed successfully.')
    await loadStatus()
  } catch (err) {
    const message = err instanceof ApiError ? err.message : 'The import could not be completed.'
    errorMessage.value = message
    errorDetails.value = err instanceof ApiError ? extractDetails(err) : []
    toast.error(message)
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void loadStatus()
})
</script>

<template>
  <AeroPageHeader
    eyebrow="Administration"
    title="Import datasets"
    subtitle="Replace the stored airport, airline and route data with CSV files."
  >
    <template #actions>
      <button class="btn btn-sm btn-glass" :disabled="statusLoading" @click="loadStatus">
        <span class="btn-label">
          <AeroIcon name="refresh" :size="13" />
          {{ statusLoading ? 'Refreshing…' : 'Refresh status' }}
        </span>
      </button>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Dataset status" subtitle="Rows currently stored by the API">
    <p
      v-if="statusError"
      class="mb-3 flex flex-wrap items-center gap-2 rounded-[7px] border border-[var(--danger-border)] bg-[var(--danger-surface)] px-2.5 py-2 text-[12px] text-[color:var(--danger-ink)]"
    >
      <span>{{ statusError }}</span>
      <button class="btn btn-sm btn-glass ml-auto" @click="loadStatus">
        <span class="btn-label">Retry</span>
      </button>
    </p>

    <div class="grid grid-cols-3 gap-3">
      <div v-for="tile in statusTiles" :key="tile.label" class="tile">
        <div class="stat-value">
          <span v-if="statusLoading" class="skeleton" style="width: 46px; height: 24px" />
          <template v-else>{{ tile.value ?? '—' }}</template>
        </div>
        <div class="stat-label">{{ tile.label }}</div>
      </div>
    </div>

    <div class="mt-4 border-t border-[rgba(255,255,255,0.65)] pt-3.5">
      <div class="field-label">Last import</div>
      <div v-if="statusLoading" class="mt-1">
        <span class="skeleton block" style="width: 190px; height: 13px" />
      </div>
      <template v-else-if="lastImport">
        <div class="text-[13px] font-normal text-[color:var(--ink)]">
          {{ formatWhen(status?.last_import_at) }}
        </div>
        <div class="mt-2 flex flex-wrap gap-1.5">
          <span
            v-for="(value, key) in lastImport.imported ?? {}"
            :key="`imported-${key}`"
            class="badge badge-mono"
          >
            {{ key }} {{ value }}
          </span>
          <span
            v-for="name in lastImport.replaced ?? []"
            :key="`replaced-${name}`"
            class="badge"
          >
            {{ name }} replaced
          </span>
        </div>
      </template>
      <div v-else class="text-[12.5px] font-light text-[color:var(--ink-soft)]">
        No import has run since the API started.
      </div>
    </div>

    <p
      v-if="!statusLoading && !statusError && datasetEmpty"
      class="mt-3 text-[12.5px] leading-relaxed font-light text-[color:var(--ink-soft)]"
    >
      The database is empty. Upload all three files together on a fresh database so every route
      can be matched to its airline and airports.
    </p>
  </AeroWindow>

  <AeroWindow
    class="mt-4"
    dense
    title="Upload CSV files"
    subtitle="At least one file is required. Each uploaded dataset replaces all stored rows."
  >
    <div class="grid gap-3 md:grid-cols-3">
      <div
        v-for="dataset in datasets"
        :key="dataset.key"
        class="rounded-[10px] border border-[rgba(255,255,255,0.75)] bg-[var(--surface-chip)] p-3"
      >
        <div class="flex items-center gap-2">
          <span class="text-[color:var(--ink-soft)]"><AeroIcon name="upload" :size="13" /></span>
          <span class="text-[13px] font-normal text-[color:var(--ink)]">{{ dataset.file }}</span>
        </div>
        <p class="mt-1 mb-2 break-words text-[11px] leading-relaxed font-light text-[color:var(--ink-soft)]">
          {{ dataset.hint }}
        </p>

        <!-- A styled label instead of the native control: the browser localises
             "Choose file" / "No file chosen", which would break the English UI. -->
        <label class="btn btn-sm btn-glass cursor-pointer" :class="{ 'pointer-events-none opacity-60': busy }">
          <span class="btn-label"><AeroIcon name="upload" :size="11" /> Choose CSV</span>
          <input
            :key="`${dataset.key}-${fileVersions[dataset.key]}`"
            type="file"
            accept=".csv"
            class="sr-only"
            :disabled="busy"
            @change="onFileChange(dataset.key, $event)"
          />
        </label>

        <p v-if="fileErrors[dataset.key]" class="mt-1.5 text-[11.5px] text-[color:var(--danger-ink)]">
          {{ fileErrors[dataset.key] }}
        </p>

        <div v-if="files[dataset.key]" class="mt-2 flex flex-wrap items-center gap-1.5">
          <span class="badge badge-mono max-w-full truncate">{{ files[dataset.key]?.name }}</span>
          <span class="text-[10.5px] font-light text-[color:var(--ink-soft)]">
            {{ formatBytes(files[dataset.key]?.size ?? 0) }}
          </span>
          <button
            class="btn btn-sm btn-glass ml-auto"
            :disabled="busy"
            @click="clearFile(dataset.key)"
          >
            <span class="btn-label"><AeroIcon name="x" :size="11" /> Clear</span>
          </button>
        </div>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
      <button class="btn" :disabled="!canSubmit" @click="submit">
        <span class="btn-label">
          <AeroIcon name="upload" :size="13" />
          {{ busy ? 'Importing…' : 'Import selected files' }}
        </span>
      </button>
      <span class="text-[11.5px] font-light text-[color:var(--ink-soft)]">
        {{ selected.length }} of 3 files selected · only .csv files are accepted
      </span>
    </div>

    <div
      v-if="errorMessage"
      class="mt-4 rounded-[7px] border border-[var(--danger-border)] bg-[var(--danger-surface)] px-3 py-2.5"
    >
      <div class="flex items-start gap-2">
        <span class="mt-[1px] shrink-0 text-[color:var(--danger-ink)]"><AeroIcon name="x" :size="13" /></span>
        <div class="min-w-0">
          <div class="text-[12.5px] leading-relaxed font-normal text-[color:var(--danger-ink)]">
            {{ errorMessage }}
          </div>

          <div v-if="errorDetails.length" class="mt-2">
            <div class="field-label mb-1 text-[color:var(--danger-ink)]">
              Validation details ({{ errorDetails.length }})
            </div>
            <ul class="m-0 list-none space-y-1 p-0">
              <li
                v-for="(detail, index) in errorDetails"
                :key="index"
                class="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 text-[11.5px] leading-relaxed font-light text-[color:var(--danger-ink)]"
              >
                <span v-if="detail.dataset" class="badge badge-mono">{{ detail.dataset }}</span>
                <span v-if="detail.field" class="font-normal">{{ detail.field }}:</span>
                <span class="min-w-0 break-words">{{ detail.issue }}</span>
                <span v-if="detail.row !== undefined" class="mono">row {{ detail.row }}</span>
                <span v-if="detail.route_id !== undefined" class="mono">
                  route {{ detail.route_id }}
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="result"
      class="mt-4 rounded-[7px] border border-[var(--success-border)] bg-[var(--success-surface)] px-3 py-2.5"
    >
      <div class="flex items-start gap-2">
        <span class="mt-[1px] shrink-0 text-[color:var(--success-ink)]"><AeroIcon name="check" :size="14" /></span>
        <div class="min-w-0">
          <div class="text-[12.5px] leading-relaxed font-normal text-[color:var(--success-ink)]">
            {{ result.message }}
          </div>

          <div
            v-if="result.imported && Object.keys(result.imported).length"
            class="mt-2 flex flex-wrap gap-1.5"
          >
            <span
              v-for="(value, key) in result.imported"
              :key="`imported-${key}`"
              class="badge badge-lime"
            >
              {{ key }} · {{ value }} imported
            </span>
          </div>

          <div v-if="(result.replaced ?? []).length" class="mt-1.5 flex flex-wrap gap-1.5">
            <span v-for="name in result.replaced ?? []" :key="`replaced-${name}`" class="badge">
              {{ name }} replaced
            </span>
          </div>

          <p v-if="result.counts" class="mt-2 text-[11.5px] font-light text-[color:var(--ink-soft)]">
            The database now holds {{ result.counts.airports }} airports,
            {{ result.counts.airlines }} airlines and {{ result.counts.routes }} routes.
          </p>
        </div>
      </div>
    </div>
  </AeroWindow>
</template>
