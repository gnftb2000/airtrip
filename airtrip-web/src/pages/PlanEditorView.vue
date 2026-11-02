<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AeroDrawer from '@/components/AeroDrawer.vue'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Route } from '@/api/types'
import { useToastStore } from '@/stores/toast'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const planId = computed(() => Number(route.params.id ?? 0))
const isEdit = computed(() => Number.isFinite(planId.value) && planId.value > 0)

const form = reactive({ name: '', departure_date: '', return_date: '' })
const selected = ref<Route[]>([])
const originalIds = ref<number[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const routeColumns: AeroColumn[] = [
  { key: 'route_id', label: 'Route', width: '72px', mono: true },
  { key: 'airline_iata', label: 'Airline', width: '86px', mono: true },
  { key: 'leg', label: 'Leg', width: '150px', mono: true },
  { key: 'stops_label', label: 'Stops', width: '92px' },
  { key: 'equipment', label: 'Equipment', width: '110px' },
  { key: 'remove', label: '', width: '52px', align: 'right' },
]

const routeRows = computed(() =>
  selected.value.map((item) => ({
    ...item,
    leg: `${item.origin_iata} → ${item.destination_iata}`,
    stops_label: item.stops === 0 ? 'Nonstop' : `${item.stops} stop${item.stops === 1 ? '' : 's'}`,
  })),
)

const airlineCount = computed(() => new Set(selected.value.map((item) => item.airline_iata)).size)

async function loadPlan(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  error.value = ''
  try {
    const plan = await api.plan(planId.value)
    form.name = plan.name
    form.departure_date = plan.departure_date
    form.return_date = plan.return_date
    let routes: Route[] = plan.routes ?? []
    if (!routes.length) {
      const page = await api.planRoutes(planId.value, { page_size: 100 })
      routes = page.items
    }
    selected.value = routes.map((item) => ({ ...item }) as Route)
    originalIds.value = selected.value.map((item) => item.route_id)
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load this plan.'
  } finally {
    loading.value = false
  }
}

onMounted(loadPlan)

// ---- route picker ---------------------------------------------------------
const pickerOpen = ref(false)
const picker = reactive({ origin: '', destination: '', airline: '', page: 1 })
const pickerRows = ref<Route[]>([])
const pickerPages = ref(1)
const pickerTotal = ref(0)
const pickerLoading = ref(false)
const picked = ref<Set<number>>(new Set())

const pickerColumns: AeroColumn[] = [
  { key: 'select', label: '', width: '34px' },
  { key: 'airline_iata', label: 'Airline', width: '82px', mono: true },
  { key: 'leg', label: 'Leg', width: '130px', mono: true },
  { key: 'stops_label', label: 'Stops', width: '82px' },
  { key: 'equipment', label: 'Equipment' },
]

const pickerRowsView = computed(() =>
  pickerRows.value.map((item) => ({
    ...item,
    leg: `${item.origin_iata} → ${item.destination_iata}`,
    stops_label: item.stops === 0 ? 'Nonstop' : `${item.stops} stop${item.stops === 1 ? '' : 's'}`,
  })),
)

const pickerKey = computed(() =>
  [picker.origin, picker.destination, picker.airline, picker.page].join('|'),
)

let timer: number | undefined

async function loadPicker(): Promise<void> {
  pickerLoading.value = true
  try {
    const result = await api.routes({
      origin: picker.origin.trim().toUpperCase() || undefined,
      destination: picker.destination.trim().toUpperCase() || undefined,
      airline: picker.airline.trim().toUpperCase() || undefined,
      page: picker.page,
      page_size: 8,
    })
    pickerRows.value = result.items
    pickerPages.value = Math.max(1, result.pages)
    pickerTotal.value = result.total
  } catch {
    pickerRows.value = []
    pickerPages.value = 1
    pickerTotal.value = 0
  } finally {
    pickerLoading.value = false
  }
}

watch(pickerKey, () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(loadPicker, 220)
})

watch(
  () => [picker.origin, picker.destination, picker.airline].join('|'),
  () => {
    if (picker.page !== 1) picker.page = 1
  },
)

watch(pickerOpen, (open) => {
  if (!open) return
  picked.value = new Set()
  picker.page = 1
  void loadPicker()
})

onBeforeUnmount(() => window.clearTimeout(timer))

function toggle(row: Route): void {
  const next = new Set(picked.value)
  if (next.has(row.route_id)) next.delete(row.route_id)
  else next.add(row.route_id)
  picked.value = next
}

function commitPicked(): void {
  const existing = new Set(selected.value.map((item) => item.route_id))
  const additions = pickerRows.value.filter(
    (item) => picked.value.has(item.route_id) && !existing.has(item.route_id),
  )
  // Selections can span pages, so fetch anything picked that is not on screen.
  const missing = [...picked.value].filter(
    (id) => !existing.has(id) && !additions.some((item) => item.route_id === id),
  )
  selected.value = [...selected.value, ...additions]
  if (missing.length) {
    void (async () => {
      for (const id of missing) {
        try {
          const item = await api.route(id)
          selected.value = [...selected.value, item]
        } catch {
          /* a route that just vanished is not worth an error */
        }
      }
    })()
  }
  pickerOpen.value = false
  toast.ok(`${additions.length + missing.length} route(s) added to the plan.`)
}

function removeRoute(routeId: number): void {
  selected.value = selected.value.filter((item) => item.route_id !== routeId)
}

// ---- save -----------------------------------------------------------------
function validate(): string {
  if (!form.name.trim()) return 'Give the plan a name.'
  if (!form.departure_date || !form.return_date) return 'Both dates are required.'
  if (form.return_date < form.departure_date) return 'The return date cannot be before departure.'
  return ''
}

async function save(): Promise<void> {
  const problem = validate()
  if (problem) {
    error.value = problem
    return
  }
  error.value = ''
  saving.value = true
  try {
    if (!isEdit.value) {
      await api.createPlan({
        name: form.name.trim(),
        departure_date: form.departure_date,
        return_date: form.return_date,
        route_ids: selected.value.map((item) => item.route_id),
      })
      toast.ok('Plan created.')
    } else {
      await api.updatePlan(planId.value, {
        name: form.name.trim(),
        departure_date: form.departure_date,
        return_date: form.return_date,
      })
      const now = new Set(selected.value.map((item) => item.route_id))
      const before = new Set(originalIds.value)
      const additions = [...now].filter((id) => !before.has(id))
      const removals = [...before].filter((id) => !now.has(id))
      if (additions.length) await api.addPlanRoutes(planId.value, additions)
      for (const id of removals) await api.removePlanRoute(planId.value, id)
      toast.ok('Plan saved.')
    }
    await router.push('/plans')
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not save the plan.'
    toast.error(error.value)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AeroPageHeader
    eyebrow="Travel plans"
    :title="isEdit ? form.name || 'Edit plan' : 'New plan'"
    subtitle="A private itinerary: dates plus the routes you want to fly."
  >
    <template #actions>
      <RouterLink to="/plans" class="btn btn-glass">
        <span class="btn-label">Cancel</span>
      </RouterLink>
      <button class="btn" :disabled="saving || loading" @click="save">
        <span class="btn-label">
          <AeroIcon name="check" :size="13" /> {{ saving ? 'Saving…' : isEdit ? 'Save plan' : 'Create plan' }}
        </span>
      </button>
    </template>
  </AeroPageHeader>

  <p
    v-if="error"
    class="mb-4 rounded-[8px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.9)] px-3 py-2 text-[12.5px] text-[#983328]"
  >
    {{ error }}
  </p>

  <div class="grid items-start gap-4 lg:grid-cols-[330px_1fr]">
    <AeroWindow title="Plan details" subtitle="Name and travel window">
      <div class="space-y-3">
        <label class="block">
          <span class="field-label">Plan name</span>
          <input v-model="form.name" class="field" placeholder="Winter loop" maxlength="80" />
        </label>
        <label class="block">
          <span class="field-label">Departure date</span>
          <input v-model="form.departure_date" type="date" class="field" />
        </label>
        <label class="block">
          <span class="field-label">Return date</span>
          <input v-model="form.return_date" type="date" class="field" />
        </label>

        <div class="grid grid-cols-3 gap-2 pt-1">
          <div class="tile">
            <div class="tile-value">{{ selected.length }}</div>
            <div class="tile-label">routes</div>
          </div>
          <div class="tile">
            <div class="tile-value">{{ airlineCount }}</div>
            <div class="tile-label">airlines</div>
          </div>
          <div class="tile">
            <div class="tile-value">{{ new Set(selected.map((s) => s.destination_iata)).size }}</div>
            <div class="tile-label">destinations</div>
          </div>
        </div>

        <p v-if="isEdit" class="text-[11.5px] leading-relaxed font-light text-[#3d7592]">
          Changes replace the stored route list: routes you add are appended, routes you remove are
          dropped. The plan is protected while it still has routes.
        </p>
      </div>
    </AeroWindow>

    <AeroWindow
      dense
      title="Routes"
      :subtitle="`${selected.length} selected · ${airlineCount} airlines`"
    >
      <template #actions>
        <button class="btn btn-sm btn-glass" @click="pickerOpen = true">
          <span class="btn-label"><AeroIcon name="plus" :size="12" /> Add routes</span>
        </button>
      </template>

      <AeroTable
        :columns="routeColumns"
        :rows="routeRows as unknown as Record<string, unknown>[]"
        row-key="route_id"
        :loading="loading"
      >
        <template #cell-route_id="{ value }">
          <span class="mono text-[#0a4260]">{{ value }}</span>
        </template>
        <template #cell-airline_iata="{ value }">
          <span class="badge badge-mono">{{ value }}</span>
        </template>
        <template #cell-remove="{ row }">
          <button
            class="btn btn-sm btn-glass"
            title="Remove from plan"
            @click.stop="removeRoute(Number(row.route_id))"
          >
            <span class="btn-label"><AeroIcon name="trash" :size="11" /></span>
          </button>
        </template>
        <template #empty>
          <AeroEmpty
            icon="route"
            title="No routes yet"
            text="A plan can be saved empty, but it is only useful once it has a flight or two."
          >
            <button class="btn btn-sm btn-glass mt-2" @click="pickerOpen = true">
              <span class="btn-label">Browse routes</span>
            </button>
          </AeroEmpty>
        </template>
      </AeroTable>
    </AeroWindow>
  </div>

  <AeroDrawer v-model="pickerOpen" title="Add routes" subtitle="Filters search the whole network">
    <div class="space-y-3">
      <div class="grid grid-cols-3 gap-2">
        <label class="block">
          <span class="field-label">Origin</span>
          <input v-model="picker.origin" class="field mono" maxlength="3" placeholder="SYD" />
        </label>
        <label class="block">
          <span class="field-label">Destination</span>
          <input v-model="picker.destination" class="field mono" maxlength="3" placeholder="MEL" />
        </label>
        <label class="block">
          <span class="field-label">Airline</span>
          <input v-model="picker.airline" class="field mono" maxlength="2" placeholder="QF" />
        </label>
      </div>

      <AeroTable
        :columns="pickerColumns"
        :rows="pickerRowsView as unknown as Record<string, unknown>[]"
        row-key="route_id"
        :loading="pickerLoading"
        clickable
        :skeleton-rows="4"
        @row-click="(row) => toggle(row as unknown as Route)"
      >
        <template #cell-select="{ row }">
          <input
            type="checkbox"
            class="checkbox"
            :checked="picked.has(Number(row.route_id))"
            @click.stop="toggle(row as unknown as Route)"
          />
        </template>
        <template #cell-airline_iata="{ value }">
          <span class="badge badge-mono">{{ value }}</span>
        </template>
      </AeroTable>

      <AeroPager
        :page="picker.page"
        :pages="pickerPages"
        :total="pickerTotal"
        :page-size="8"
        unit="routes"
        @update:page="(value) => (picker.page = value)"
      />

      <div class="flex items-center gap-2 pt-1">
        <span class="text-[12px] font-light text-[#2f6683]">{{ picked.size }} selected</span>
        <button class="btn ml-auto" :disabled="!picked.size" @click="commitPicked">
          <span class="btn-label">Add to plan</span>
        </button>
      </div>
    </div>
  </AeroDrawer>
</template>
