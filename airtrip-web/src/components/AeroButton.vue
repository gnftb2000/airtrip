<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'glass' | 'aqua' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    type?: 'button' | 'submit'
    disabled?: boolean
    iconOnly?: boolean
    block?: boolean
  }>(),
  { variant: 'primary', size: 'md', type: 'button', disabled: false, iconOnly: false, block: false },
)

const classes = computed(() => [
  'btn',
  props.variant === 'glass' && 'btn-glass',
  props.variant === 'aqua' && 'btn-aqua',
  props.variant === 'danger' && 'btn-danger',
  props.size === 'sm' && 'btn-sm',
  props.size === 'lg' && 'btn-lg',
  props.iconOnly && 'btn-icon',
  props.block && 'w-full',
])
</script>

<template>
  <button :class="classes" :type="type" :disabled="disabled">
    <span class="btn-label"><slot /></span>
  </button>
</template>
