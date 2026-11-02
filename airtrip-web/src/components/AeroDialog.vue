<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    subtitle?: string
    width?: string
  }>(),
  { title: '', subtitle: '', width: '440px' },
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
    <Transition name="dialog">
      <div v-if="modelValue" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="dialog-veil absolute inset-0" @click="close" />
        <section class="win relative z-10 w-full" :style="{ maxWidth: width }" role="dialog" aria-modal="true">
          <header class="win-bar">
            <div class="min-w-0">
              <div class="win-title truncate">{{ title }}</div>
              <div v-if="subtitle" class="win-sub truncate">{{ subtitle }}</div>
            </div>
            <div class="ml-auto flex items-center gap-2">
              <button class="btn btn-icon btn-glass" aria-label="Close" @click="close">
                <span class="btn-label"><span class="text-[15px] leading-none">×</span></span>
              </button>
            </div>
          </header>
          <div class="win-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="win-foot">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
