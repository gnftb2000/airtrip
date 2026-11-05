<script setup lang="ts">
import { computed } from 'vue'
import AeroIcon from './AeroIcon.vue'

const props = withDefaults(
  defineProps<{
    page: number
    pages: number
    total: number
    pageSize: number
    unit?: string
  }>(),
  { unit: 'records' },
)

const emit = defineEmits<{ (e: 'update:page', page: number): void }>()

const from = computed(() => (props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1))
const to = computed(() => Math.min(props.page * props.pageSize, props.total))

const visible = computed(() => {
  const span = 5
  const start = Math.max(1, Math.min(props.page - 2, Math.max(1, props.pages - span + 1)))
  return Array.from({ length: Math.min(span, props.pages) }, (_, i) => start + i)
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-3">
    <span class="text-[12px] font-light text-[color:var(--ink-soft)]">
      Showing {{ from }}–{{ to }} of {{ total }} {{ unit }}
    </span>
    <div class="ml-auto flex items-center gap-1.5">
      <button class="page-btn" :disabled="page <= 1" @click="emit('update:page', page - 1)">
        <AeroIcon name="chevron-left" :size="13" />
      </button>
      <button
        v-for="n in visible"
        :key="n"
        class="page-btn"
        :class="{ 'page-btn-active': n === page }"
        @click="emit('update:page', n)"
      >
        {{ n }}
      </button>
      <button class="page-btn" :disabled="page >= pages" @click="emit('update:page', page + 1)">
        <AeroIcon name="chevron-right" :size="13" />
      </button>
    </div>
  </div>
</template>
