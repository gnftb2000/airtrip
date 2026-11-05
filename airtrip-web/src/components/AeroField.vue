<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    hint?: string
    for?: string
    error?: string
  }>(),
  { label: '', hint: '', for: undefined, error: '' },
)
</script>

<template>
  <label class="block" :for="$props.for">
    <span v-if="label" class="field-label">{{ label }}</span>
    <slot />
    <span v-if="error" class="mt-1 block text-[11.5px] text-[color:var(--danger-ink)]">{{ error }}</span>
    <span v-else-if="hint" class="field-hint">{{ hint }}</span>
  </label>
</template>
