<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    variant?: 'light' | 'dark'
    padded?: boolean
    dense?: boolean
  }>(),
  { title: '', subtitle: '', variant: 'light', padded: true, dense: false },
)
</script>

<template>
  <section class="win" :class="{ 'win-dark': variant === 'dark', 'win-dense': dense }">
    <header v-if="title || $slots.icon || $slots.actions" class="win-bar">
      <slot name="icon" />
      <div class="min-w-0">
        <div class="win-title truncate">{{ title }}</div>
        <div v-if="subtitle" class="win-sub truncate">{{ subtitle }}</div>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <slot name="actions" />
      </div>
    </header>

    <div :class="padded ? 'win-body' : ''">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="win-foot">
      <slot name="footer" />
    </footer>
  </section>
</template>
