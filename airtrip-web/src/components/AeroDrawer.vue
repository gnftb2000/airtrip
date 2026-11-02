<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    subtitle?: string
    width?: string
  }>(),
  { title: '', subtitle: '', width: '420px' },
)

const emit = defineEmits<{ (e: 'update:modelValue', open: boolean): void }>()

function close(): void {
  emit('update:modelValue', false)
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) window.addEventListener('keydown', onKey)
    else window.removeEventListener('keydown', onKey)
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="modelValue" class="fixed inset-0 z-50">
        <div class="dialog-veil absolute inset-0" @click="close" />
        <aside
          class="win win-dark drawer-panel absolute top-0 right-0 bottom-0 flex w-full flex-col"
          :style="{ maxWidth: width }"
          role="dialog"
          aria-modal="true"
        >
          <header class="win-bar">
            <div class="min-w-0">
              <div class="win-title truncate">{{ title }}</div>
              <div v-if="subtitle" class="win-sub truncate">{{ subtitle }}</div>
            </div>
            <div class="ml-auto flex items-center gap-2">
              <button class="btn btn-sm btn-glass" @click="close">
                <span class="btn-label">Close</span>
              </button>
            </div>
          </header>
          <div class="win-body aero-scroll flex-1 overflow-y-auto">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="win-foot">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
