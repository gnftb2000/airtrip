<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AeroDialog from '@/components/AeroDialog.vue'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError, downloadBlob } from '@/api/client'
import type { TravelPlan } from '@/api/types'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const toast = useToastStore()

const plans = ref<TravelPlan[]>([])
const page = ref(1)
const pageSize = 10
const total = ref(0)
const pages = ref(1)
const loading = ref(true)
const error = ref('')
const exporting = ref<'' | 'json' | 'png'>('')

const deleteOpen = ref(false)
const deleteTarget = ref<TravelPlan | null>(null)
const deleting = ref(false)

const columns: AeroColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'departure_date', label: 'Departure', width: '140px' },
  { key: 'return_date', label: 'Return', width: '140px' },
  { key: 'route_count', label: 'Routes', width: '86px', align: 'right', mono: true },
  { key: 'updated_label', label: 'Updated', width: '180px' },
  { key: 'actions', label: 'Actions', width: '168px', align: 'right' },
]

const dayFormatter = new Intl.DateTimeFormat('en-AU', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

function formatDate(value: string): string {
  if (!value) return '—'
  // Dates arrive as YYYY-MM-DD; parse as a calendar day, not a UTC instant.
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (match) return dayFormatter.format(new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dayFormatter.format(date)
}

function formatStamp(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('en-AU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const rows = computed<Record<string, unknown>[]>(() =>
  plans.value.map((plan) => ({
    plan_id: plan.plan_id,
    name: plan.name,
    edit_path: `/plans/${plan.plan_id}/edit`,
    departure_date: formatDate(plan.departure_date),
    return_date: formatDate(plan.return_date),
    route_count: plan.route_count,
    updated_label: formatStamp(plan.updated_at),
  })),
)

let timer: number | undefined

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await api.plans({ page: page.value, page_size: pageSize })
    plans.value = result.items
    total.value = result.total
    pages.value = Math.max(1, result.pages)
    if (page.value > pages.value) page.value = pages.value
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load your travel plans.'
    plans.value = []
    total.value = 0
    pages.value = 1
  } finally {
    loading.value = false
  }
}

watch(page, () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(load, 120)
})

onBeforeUnmount(() => window.clearTimeout(timer))

void load()

function openPlan(row: Record<string, unknown>): void {
  router.push(String(row.edit_path))
}

function askDelete(row: Record<string, unknown>): void {
  const id = Number(row.plan_id)
  const target = plans.value.find((plan) => plan.plan_id === id)
  if (!target) return
  deleteTarget.value = target
  deleteOpen.value = true
}

function closeDelete(): void {
  if (deleting.value) return
  deleteOpen.value = false
  deleteTarget.value = null
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await api.deletePlan(deleteTarget.value.plan_id)
    toast.ok('Travel plan deleted.')
    const wasLastOnPage = plans.value.length === 1 && page.value > 1
    deleteOpen.value = false
    deleteTarget.value = null
    if (wasLastOnPage) page.value -= 1
    else await load()
  } catch (err) {
    // Plans that still have routes cannot be removed: surface the API's own
    // message (a 409 would arrive here) instead of a generic failure.
    toast.error(err instanceof ApiError ? err.message : 'Could not delete this travel plan.')
  } finally {
    deleting.value = false
  }
}

function exportStamp(): string {
  return new Date().toISOString().slice(0, 10)
}

async function exportJson(): Promise<void> {
  if (exporting.value) return
  exporting.value = 'json'
  try {
    const data = await api.exportPlanJson()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    downloadBlob(blob, `airtrip-plans-${data.account}-${exportStamp()}.json`)
    const count = data.plan_count
    toast.ok(`Exported ${count} plan${count === 1 ? '' : 's'} as JSON.`)
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : 'Could not export your plans as JSON.')
  } finally {
    exporting.value = ''
  }
}

async function exportImage(): Promise<void> {
  if (exporting.value) return
  exporting.value = 'png'
  try {
    const blob = await api.exportPlanImage()
    downloadBlob(blob, `airtrip-plans-timeline-${exportStamp()}.png`)
    toast.ok('Exported the plan timeline as PNG.')
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : 'Could not export the plan timeline.')
  } finally {
    exporting.value = ''
  }
}
</script>

<template>
  <AeroPageHeader
    eyebrow="Itineraries"
    title="Travel plans"
    subtitle="Your private itineraries, with the route list behind each one."
  >
    <template #actions>
      <button class="btn btn-glass" :disabled="exporting !== '' || loading" @click="exportJson">
        <span class="btn-label">
          <AeroIcon name="download" :size="13" />
          {{ exporting === 'json' ? 'Exporting…' : 'Export JSON' }}
        </span>
      </button>
      <button class="btn btn-glass" :disabled="exporting !== '' || loading" @click="exportImage">
        <span class="btn-label">
          <AeroIcon name="download" :size="13" />
          {{ exporting === 'png' ? 'Exporting…' : 'Export PNG' }}
        </span>
      </button>
      <RouterLink to="/plans/new" class="btn">
        <span class="btn-label"><AeroIcon name="plus" :size="13" /> New plan</span>
      </RouterLink>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Your plans" :subtitle="`${total} plans · page ${page} of ${pages}`">
    <template #actions>
      <span class="badge"><AeroIcon name="plan" :size="11" /> private</span>
    </template>

    <p
      v-if="error"
      class="mb-3 flex flex-wrap items-center gap-2 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
    >
      <span>{{ error }}</span>
      <button class="btn btn-sm btn-glass ml-auto" @click="load">
        <span class="btn-label">Retry</span>
      </button>
    </p>

    <AeroTable
      :columns="columns"
      :rows="rows"
      row-key="plan_id"
      :loading="loading"
      clickable
      :skeleton-rows="5"
      @row-click="openPlan"
    >
      <template #cell-name="{ row }">
        <RouterLink
          :to="String(row.edit_path)"
          class="font-normal text-[#0b5a86] underline decoration-[rgba(11,90,134,0.35)] underline-offset-2 hover:decoration-[#0b5a86]"
          @click.stop
        >
          {{ row.name }}
        </RouterLink>
      </template>
      <template #cell-departure_date="{ value }">
        <span class="mono">{{ value }}</span>
      </template>
      <template #cell-return_date="{ value }">
        <span class="mono">{{ value }}</span>
      </template>
      <template #cell-route_count="{ value }">
        <span class="mono">{{ value }}</span>
      </template>
      <template #cell-updated_label="{ value }">
        <span class="font-light text-[#255b78]">{{ value }}</span>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex items-center justify-end gap-1.5">
          <button class="btn btn-sm btn-glass" @click.stop="openPlan(row)">
            <span class="btn-label">Edit</span>
          </button>
          <button class="btn btn-sm btn-danger" @click.stop="askDelete(row)">
            <span class="btn-label">Delete</span>
          </button>
        </div>
      </template>
      <template #empty>
        <AeroEmpty
          icon="plan"
          title="No travel plans yet"
          text="Create a plan, then add the routes you want to fly. Plans are private to your account."
        >
          <RouterLink to="/plans/new" class="btn btn-sm mt-2">
            <span class="btn-label"><AeroIcon name="plus" :size="12" /> New plan</span>
          </RouterLink>
        </AeroEmpty>
      </template>
    </AeroTable>

    <template #footer>
      <AeroPager
        :page="page"
        :pages="pages"
        :total="total"
        :page-size="pageSize"
        unit="plans"
        @update:page="(value) => (page = value)"
      />
    </template>
  </AeroWindow>

  <AeroDialog
    v-model="deleteOpen"
    title="Delete travel plan"
    :subtitle="deleteTarget?.name ?? ''"
    width="440px"
  >
    <p class="text-[13px] leading-relaxed font-light text-[#255b78]">
      This plan and its route list will be removed. The routes themselves stay in the network, so
      other plans that use them are not affected.
    </p>
    <p v-if="deleteTarget" class="mt-2 text-[12.5px] font-light text-[#2f6683]">
      {{ deleteTarget.route_count }} route{{ deleteTarget.route_count === 1 ? '' : 's' }} in this
      plan.
    </p>
    <p class="mt-2 text-[12px] font-light text-[#983328]">This cannot be undone.</p>

    <template #footer>
      <button class="btn btn-sm btn-glass" :disabled="deleting" @click="closeDelete">
        <span class="btn-label">Cancel</span>
      </button>
      <button class="btn btn-sm btn-danger ml-auto" :disabled="deleting" @click="confirmDelete">
        <span class="btn-label">
          <AeroIcon name="trash" :size="12" />
          {{ deleting ? 'Deleting…' : 'Delete plan' }}
        </span>
      </button>
    </template>
  </AeroDialog>
</template>
