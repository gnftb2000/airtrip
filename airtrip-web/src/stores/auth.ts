import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, readToken, writeToken } from '@/api/client'
import type { Account } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const account = ref<Account | null>(null)
  const token = ref<string | null>(readToken())
  const ready = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && account.value))
  const isAdmin = computed(() => account.value?.role === 'admin')

  async function login(username: string, password: string): Promise<void> {
    const response = await api.login(username, password)
    writeToken(response.access_token)
    token.value = response.access_token
    account.value = response.account
  }

  /** Restores the session from the stored token; safe to call once at boot. */
  async function hydrate(): Promise<void> {
    if (ready.value) return
    if (token.value) {
      try {
        account.value = await api.me()
      } catch {
        logout()
      }
    }
    ready.value = true
  }

  function logout(): void {
    writeToken(null)
    token.value = null
    account.value = null
  }

  return { account, token, ready, isAuthenticated, isAdmin, login, hydrate, logout }
})
