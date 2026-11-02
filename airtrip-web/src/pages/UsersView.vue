<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AeroDialog from '@/components/AeroDialog.vue'
import AeroEmpty from '@/components/AeroEmpty.vue'
import AeroIcon from '@/components/AeroIcon.vue'
import AeroPageHeader from '@/components/AeroPageHeader.vue'
import AeroPager from '@/components/AeroPager.vue'
import AeroTable, { type AeroColumn } from '@/components/AeroTable.vue'
import AeroWindow from '@/components/AeroWindow.vue'
import { api, ApiError } from '@/api/client'
import type { Account } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

type RoleFilter = '' | 'admin' | 'user'
type ActiveFilter = '' | 'true' | 'false'

const auth = useAuthStore()
const toast = useToastStore()

const filters = reactive<{ q: string; role: RoleFilter; active: ActiveFilter }>({
  q: '',
  role: '',
  active: '',
})
const page = ref(1)
const pageSize = ref(10)
const rows = ref<Account[]>([])
const total = ref(0)
const pages = ref(1)
const loading = ref(true)
const error = ref('')
const busyUser = ref<string | null>(null)

const columns: AeroColumn[] = [
  { key: 'username', label: 'Username' },
  { key: 'role', label: 'Role', width: '96px' },
  { key: 'is_active', label: 'Active', width: '104px' },
  { key: 'created_at', label: 'Created', width: '174px' },
  { key: 'actions', label: 'Actions', width: '196px', align: 'right' },
]

const createOpen = ref(false)
const createForm = reactive({ username: '', password: '' })
const createError = ref('')
const creating = ref(false)

const deleteOpen = ref(false)
const deleteTarget = ref<Account | null>(null)
const deleting = ref(false)

const hasFilters = computed(
  () => filters.q.trim() !== '' || filters.role !== '' || filters.active !== '',
)

const dateFormatter = new Intl.DateTimeFormat('en-AU', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDate(value: unknown): string {
  if (!value) return '—'
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value) : dateFormatter.format(date)
}

function asAccount(row: Record<string, unknown>): Account {
  return row as unknown as Account
}

function isSelf(account: Account): boolean {
  return auth.account?.username === account.username
}

function canDelete(account: Account): boolean {
  return !isSelf(account) && account.role !== 'admin'
}

function canToggle(account: Account): boolean {
  return account.role !== 'admin'
}

function deleteTitle(account: Account): string {
  if (isSelf(account)) return 'You cannot delete your own account.'
  if (account.role === 'admin') return 'The administrator account cannot be deleted.'
  return 'Delete this account'
}

function toggleTitle(account: Account): string {
  if (account.role === 'admin') return 'The administrator account cannot be deactivated.'
  return account.is_active ? 'Deactivate this account' : 'Activate this account'
}

const queryKey = computed(() =>
  [filters.q, filters.role, filters.active, page.value, pageSize.value].join('|'),
)

let timer: number | undefined

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await api.users({
      q: filters.q.trim() || undefined,
      role: filters.role || undefined,
      is_active: filters.active === '' ? undefined : filters.active === 'true',
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = result.items
    total.value = result.total
    pages.value = Math.max(1, result.pages)
    if (page.value > pages.value) page.value = pages.value
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load the accounts.'
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
  () => [filters.q, filters.role, filters.active, pageSize.value].join('|'),
  () => {
    if (page.value !== 1) page.value = 1
  },
)

onBeforeUnmount(() => window.clearTimeout(timer))

function resetFilters(): void {
  filters.q = ''
  filters.role = ''
  filters.active = ''
  page.value = 1
}

function openCreate(): void {
  createForm.username = ''
  createForm.password = ''
  createError.value = ''
  createOpen.value = true
}

async function submitCreate(): Promise<void> {
  createError.value = ''
  const username = createForm.username.trim()
  if (username.length < 3 || username.length > 32) {
    createError.value = 'Username must be between 3 and 32 characters.'
    return
  }
  if (createForm.password.length < 4 || createForm.password.length > 128) {
    createError.value = 'Password must be between 4 and 128 characters.'
    return
  }

  creating.value = true
  try {
    const account = await api.createUser({
      username,
      password: createForm.password,
      role: 'user',
    })
    createOpen.value = false
    toast.ok(`Account "${account.username}" created.`)
    await load()
  } catch (err) {
    const message = err instanceof ApiError ? err.message : 'Could not create the account.'
    createError.value = message
    toast.error(message)
  } finally {
    creating.value = false
  }
}

async function toggleActive(account: Account): Promise<void> {
  if (!canToggle(account) || busyUser.value !== null) return
  busyUser.value = account.username
  const wasActive = account.is_active
  try {
    await api.updateUser(account.username, { is_active: !wasActive })
    toast.ok(`Account "${account.username}" ${wasActive ? 'deactivated' : 'activated'}.`)
    await load()
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : 'Could not update the account.')
  } finally {
    busyUser.value = null
  }
}

function askDelete(account: Account): void {
  if (!canDelete(account)) return
  deleteTarget.value = account
  deleteOpen.value = true
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target || !canDelete(target)) return
  deleting.value = true
  try {
    await api.deleteUser(target.username)
    toast.ok(`Account "${target.username}" deleted.`)
    deleteOpen.value = false
    deleteTarget.value = null
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : 'Could not delete the account.')
  } finally {
    deleting.value = false
  }
}

watch(deleteOpen, (open) => {
  if (!open) deleteTarget.value = null
})
</script>

<template>
  <AeroPageHeader
    eyebrow="Administration"
    title="Accounts"
    subtitle="Create standard user accounts, deactivate access, or remove an account entirely."
  >
    <template #actions>
      <button class="btn btn-sm btn-glass" :disabled="loading" @click="load">
        <span class="btn-label"><AeroIcon name="refresh" :size="13" /> Refresh</span>
      </button>
      <button class="btn btn-sm" @click="openCreate">
        <span class="btn-label"><AeroIcon name="plus" :size="13" /> New account</span>
      </button>
    </template>
  </AeroPageHeader>

  <AeroWindow dense title="Search accounts" subtitle="Filters apply as you type">
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label class="block sm:col-span-2">
        <span class="field-label">Search</span>
        <input v-model="filters.q" class="field" placeholder="Username…" />
      </label>
      <label class="block">
        <span class="field-label">Role</span>
        <span class="select-wrap">
          <select v-model="filters.role" class="field">
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
          </select>
        </span>
      </label>
      <label class="block">
        <span class="field-label">Status</span>
        <span class="select-wrap">
          <select v-model="filters.active" class="field">
            <option value="">All accounts</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
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
      <div class="flex items-end pb-1">
        <button class="btn btn-sm btn-glass" @click="resetFilters">
          <span class="btn-label"><AeroIcon name="filter" :size="12" /> Reset filters</span>
        </button>
      </div>
    </div>
  </AeroWindow>

  <AeroWindow
    class="mt-4"
    dense
    title="Accounts"
    :subtitle="`${total} accounts · page ${page} of ${pages}`"
  >
    <template #actions>
      <span class="badge">
        <AeroIcon name="users" :size="11" /> {{ total }} total
      </span>
    </template>

    <div
      v-if="error"
      class="mb-3 flex flex-wrap items-center gap-2 rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
    >
      <span>{{ error }}</span>
      <button class="btn btn-sm btn-glass ml-auto" @click="load">
        <span class="btn-label">Retry</span>
      </button>
    </div>

    <AeroTable
      :columns="columns"
      :rows="rows as unknown as Record<string, unknown>[]"
      row-key="id"
      :loading="loading"
    >
      <template #cell-username="{ value }">
        <span class="font-normal text-[#08354f]">{{ value }}</span>
      </template>

      <template #cell-role="{ value }">
        <span class="badge" :class="{ 'badge-lime': value === 'admin' }">
          <AeroIcon :name="value === 'admin' ? 'users' : 'sparkle'" :size="10" />
          {{ value === 'admin' ? 'Admin' : 'User' }}
        </span>
      </template>

      <template #cell-is_active="{ value }">
        <span class="badge" :class="{ 'badge-aqua': value === true }">
          <AeroIcon :name="value === true ? 'check' : 'x'" :size="10" />
          {{ value === true ? 'Active' : 'Inactive' }}
        </span>
      </template>

      <template #cell-created_at="{ value }">
        <span class="text-[12px] font-light text-[#2f6683]">{{ formatDate(value) }}</span>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex items-center justify-end gap-1.5">
          <button
            class="btn btn-sm btn-glass"
            :disabled="!canToggle(asAccount(row)) || busyUser !== null"
            :title="toggleTitle(asAccount(row))"
            @click.stop="toggleActive(asAccount(row))"
          >
            <span class="btn-label">
              <AeroIcon :name="row.is_active === true ? 'x' : 'check'" :size="11" />
              {{ row.is_active === true ? 'Deactivate' : 'Activate' }}
            </span>
          </button>
          <button
            class="btn btn-sm btn-danger"
            :disabled="!canDelete(asAccount(row)) || busyUser !== null"
            :title="deleteTitle(asAccount(row))"
            @click.stop="askDelete(asAccount(row))"
          >
            <span class="btn-label"><AeroIcon name="trash" :size="11" /> Delete</span>
          </button>
        </div>
      </template>

      <template #empty>
        <AeroEmpty
          icon="users"
          :title="hasFilters ? 'No accounts match' : 'No accounts yet'"
          :text="
            hasFilters
              ? 'Try a different search, or clear the filters to see every account.'
              : 'Create the first standard user account to let another traveller sign in.'
          "
        >
          <button v-if="hasFilters" class="btn btn-sm btn-glass mt-2" @click="resetFilters">
            <span class="btn-label">Clear filters</span>
          </button>
          <button v-else class="btn btn-sm mt-2" @click="openCreate">
            <span class="btn-label"><AeroIcon name="plus" :size="12" /> New account</span>
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
        unit="accounts"
        @update:page="(value) => (page = value)"
      />
    </template>
  </AeroWindow>

  <!-- create account -->
  <AeroDialog
    v-model="createOpen"
    title="New account"
    subtitle="Standard user access"
    width="420px"
  >
    <form class="space-y-3.5" @submit.prevent="submitCreate">
      <label class="block">
        <span class="field-label">Username</span>
        <input
          v-model="createForm.username"
          class="field"
          placeholder="e.g. jane.doe"
          autocomplete="off"
          required
        />
        <span class="field-hint">3–32 characters: letters, numbers, dot, dash, underscore.</span>
      </label>

      <label class="block">
        <span class="field-label">Password</span>
        <input
          v-model="createForm.password"
          type="password"
          class="field"
          placeholder="At least 4 characters"
          autocomplete="new-password"
          required
        />
        <span class="field-hint">4–128 characters. Stored only as a password hash.</span>
      </label>

      <div>
        <span class="field-label">Role</span>
        <span class="badge badge-lime"><AeroIcon name="sparkle" :size="10" /> User</span>
        <span class="field-hint">New accounts are always created with standard user access.</span>
      </div>

      <p
        v-if="createError"
        class="rounded-[7px] border border-[#e2b0a8] bg-[rgba(255,238,235,0.85)] px-2.5 py-2 text-[12px] text-[#983328]"
      >
        {{ createError }}
      </p>

      <button type="submit" class="hidden" aria-hidden="true" />
    </form>

    <template #footer>
      <span class="text-[11.5px] font-light text-[#2f6f92]">The password is never shown again.</span>
      <div class="ml-auto flex items-center gap-2">
        <button class="btn btn-sm btn-glass" @click="createOpen = false">
          <span class="btn-label">Cancel</span>
        </button>
        <button class="btn btn-sm" :disabled="creating" @click="submitCreate">
          <span class="btn-label">{{ creating ? 'Creating…' : 'Create account' }}</span>
        </button>
      </div>
    </template>
  </AeroDialog>

  <!-- delete confirmation -->
  <AeroDialog
    v-model="deleteOpen"
    title="Delete account"
    subtitle="This cannot be undone"
    width="420px"
  >
    <div class="flex items-start gap-3">
      <div
        class="orb shrink-0"
        style="
          width: 36px;
          height: 36px;
          background: radial-gradient(
            circle at 32% 26%,
            #fff 0%,
            #ffe1e1 18%,
            #f78d8d 46%,
            #d63c3c 72%,
            #941e1e 100%
          );
        "
      >
        <AeroIcon name="trash" :size="16" />
      </div>
      <div class="min-w-0">
        <div class="text-[14px] font-normal text-[#0a4260]">
          Delete “{{ deleteTarget?.username }}”?
        </div>
        <p class="mt-1 text-[12.5px] leading-relaxed font-light text-[#1d4d6b]">
          The account and every travel plan it created will be removed. This action cannot be
          reversed.
        </p>
      </div>
    </div>

    <template #footer>
      <div class="ml-auto flex items-center gap-2">
        <button class="btn btn-sm btn-glass" :disabled="deleting" @click="deleteOpen = false">
          <span class="btn-label">Keep account</span>
        </button>
        <button class="btn btn-sm btn-danger" :disabled="deleting" @click="confirmDelete">
          <span class="btn-label">{{ deleting ? 'Deleting…' : 'Delete account' }}</span>
        </button>
      </div>
    </template>
  </AeroDialog>
</template>
