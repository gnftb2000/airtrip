<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AeroIcon from '@/components/AeroIcon.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mobileOpen = ref(false)

interface NavItem {
  to: string
  label: string
  icon: string
  admin?: boolean
  match: string
}

const nav: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: 'gauge', match: '/dashboard' },
  { to: '/airports', label: 'Airports', icon: 'tower', match: '/airports' },
  { to: '/airlines', label: 'Airlines', icon: 'globe', match: '/airlines' },
  { to: '/routes', label: 'Routes', icon: 'route', match: '/routes' },
  { to: '/plans', label: 'Travel plans', icon: 'plan', match: '/plans' },
  { to: '/import', label: 'Datasets', icon: 'upload', match: '/import', admin: true },
  { to: '/users', label: 'Accounts', icon: 'users', match: '/users', admin: true },
]

const items = computed(() => nav.filter((item) => !item.admin || auth.isAdmin))

function isActive(item: NavItem): boolean {
  return route.path === item.match || route.path.startsWith(`${item.match}/`)
}

function signOut(): void {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex min-h-screen flex-col gap-4 lg:flex-row lg:items-start lg:gap-5">
    <!-- sidebar -->
    <aside class="hidden w-[218px] shrink-0 lg:sticky lg:top-6 lg:block">
      <section class="win">
        <div class="flex items-center gap-2.5 px-3.5 py-3">
          <div class="orb sweep" style="width: 34px; height: 34px">
            <AeroIcon name="plane" :size="17" />
          </div>
          <div class="min-w-0">
            <div class="text-[14px] leading-tight font-normal text-[color:var(--ink)]">AirTrip</div>
            <div class="text-[10.5px] font-light text-[color:var(--ink-soft)]">Flight network explorer</div>
          </div>
        </div>
        <nav class="flex flex-col gap-1 px-2.5 pb-3">
          <RouterLink
            v-for="item in items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ 'nav-item-active': isActive(item) }"
          >
            <AeroIcon :name="item.icon" :size="15" />
            <span class="truncate">{{ item.label }}</span>
          </RouterLink>
        </nav>
        <div class="flex items-center gap-2 border-t border-white/60 px-3 py-2.5">
          <div class="min-w-0 flex-1">
            <div class="truncate text-[12px] font-normal text-[color:var(--ink)]">{{ auth.account?.username }}</div>
            <div class="text-[10.5px] font-light text-[color:var(--ink-soft)]">
              {{ auth.isAdmin ? 'Administrator' : 'Member' }}
            </div>
          </div>
          <button class="btn btn-sm btn-glass" title="Sign out" @click="signOut">
            <span class="btn-label"><AeroIcon name="logout" :size="13" /></span>
          </button>
        </div>
      </section>
    </aside>

    <!-- mobile top bar -->
    <div class="flex items-center gap-2 lg:hidden">
      <section class="win flex w-full items-center gap-2 px-3 py-2">
        <div class="orb" style="width: 28px; height: 28px">
          <AeroIcon name="plane" :size="14" />
        </div>
        <div class="text-[13.5px] font-normal text-[color:var(--ink)]">AirTrip</div>
        <button class="btn btn-sm btn-glass ml-auto" @click="mobileOpen = !mobileOpen">
          <span class="btn-label">{{ mobileOpen ? 'Close' : 'Menu' }}</span>
        </button>
      </section>
    </div>

    <nav v-if="mobileOpen" class="nav-sheet lg:hidden">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :class="{ 'nav-item-active': isActive(item) }"
        @click="mobileOpen = false"
      >
        <AeroIcon :name="item.icon" :size="15" />
        <span>{{ item.label }}</span>
      </RouterLink>
      <button class="nav-item" @click="signOut">
        <AeroIcon name="logout" :size="15" />
        <span>Sign out</span>
      </button>
    </nav>

    <main class="min-w-0 flex-1 pb-10">
      <RouterView />
    </main>
  </div>
</template>
