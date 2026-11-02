import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastKind = 'ok' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  text: string
}

let nextId = 1

export const useToastStore = defineStore('toast', () => {
  const items = ref<Toast[]>([])

  function dismiss(id: number): void {
    items.value = items.value.filter((t) => t.id !== id)
  }

  function push(text: string, kind: ToastKind = 'info', ttl = 4200): void {
    const id = nextId++
    items.value.push({ id, kind, text })
    window.setTimeout(() => dismiss(id), ttl)
  }

  const ok = (text: string) => push(text, 'ok')
  const error = (text: string) => push(text, 'error', 6000)
  const info = (text: string) => push(text, 'info')

  return { items, push, dismiss, ok, error, info }
})
