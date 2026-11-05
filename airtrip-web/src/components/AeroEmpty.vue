<script setup lang="ts">
import AeroIcon from './AeroIcon.vue'

withDefaults(
  defineProps<{
    icon?: string
    title?: string
    text?: string
  }>(),
  { icon: 'search', title: 'Nothing here yet', text: '' },
)
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
    <div class="orb" style="width: 44px; height: 44px">
      <AeroIcon :name="icon" :size="20" />
    </div>
    <div class="text-[14.5px] font-normal text-[color:var(--ink)]">{{ title }}</div>
    <p v-if="text" class="max-w-[380px] text-[12.5px] leading-relaxed font-light text-[color:var(--ink-soft)]">
      {{ text }}
    </p>
    <slot />
  </div>
</template>
