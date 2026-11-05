<script setup lang="ts">
withDefaults(defineProps<{ title: string; subtitle?: string; eyebrow?: string }>(), {
  subtitle: '',
  eyebrow: '',
})
</script>

<template>
  <div class="mb-4 flex flex-wrap items-end gap-3">
    <div class="min-w-0">
      <div v-if="eyebrow" class="mb-1 text-[10.5px] font-normal tracking-[0.16em] text-[color:var(--ink-soft)] uppercase">
        {{ eyebrow }}
      </div>
      <h1 class="text-[24px] leading-tight font-light tracking-[-0.2px] text-[color:var(--ink)]">{{ title }}</h1>
      <p v-if="subtitle" class="mt-1 text-[13px] font-light text-[color:var(--ink-soft)]">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="ml-auto flex flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
