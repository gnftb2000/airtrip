<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AeroIcon from '@/components/AeroIcon.vue'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('admin')
const password = ref('admin')
const busy = ref(false)
const error = ref('')

async function submit(): Promise<void> {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : '/dashboard'
    await router.replace(next)
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Sign-in failed.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="grid min-h-[calc(100vh-96px)] place-items-center px-2">
    <section class="win win-dark w-full max-w-[380px]">
      <header class="win-bar">
        <div class="min-w-0">
          <div class="win-title">AirTrip</div>
          <div class="win-sub">Flight network explorer</div>
        </div>
        <div class="ml-auto orb sweep" style="width: 34px; height: 34px">
          <AeroIcon name="plane" :size="17" />
        </div>
      </header>
      <form class="win-body space-y-3.5" @submit.prevent="submit">
        <p class="text-[12.5px] leading-relaxed font-light text-[color:var(--ink-soft)]">
          Sign in to browse airports, airlines and routes, and to keep your own travel plans.
        </p>

        <label class="block">
          <span class="field-label">Username</span>
          <input v-model="username" class="field" autocomplete="username" required />
        </label>

        <label class="block">
          <span class="field-label">Password</span>
          <input v-model="password" type="password" class="field" autocomplete="current-password" required />
        </label>

        <p
          v-if="error"
          class="rounded-[7px] border border-[var(--danger-border)] bg-[var(--danger-surface)] px-2.5 py-2 text-[12px] text-[color:var(--danger-ink)]"
        >
          {{ error }}
        </p>

        <button type="submit" class="btn btn-lg w-full" :disabled="busy">
          <span class="btn-label">{{ busy ? 'Signing in…' : 'Sign in' }}</span>
        </button>

        <p class="text-center text-[11px] font-light text-[color:var(--ink-soft)]">
          Seeded accounts: <span class="mono">admin / admin</span> ·
          <span class="mono">user / user</span>
        </p>
      </form>
    </section>
  </div>
</template>
