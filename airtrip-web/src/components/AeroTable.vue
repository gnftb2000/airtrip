<script setup lang="ts">
import AeroEmpty from './AeroEmpty.vue'

export interface AeroColumn {
  key: string
  label: string
  width?: string
  align?: 'left' | 'right' | 'center'
  mono?: boolean
}

const props = withDefaults(
  defineProps<{
    columns: AeroColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    loading?: boolean
    clickable?: boolean
    skeletonRows?: number
  }>(),
  { rowKey: 'id', loading: false, clickable: false, skeletonRows: 5 },
)

const emit = defineEmits<{ (e: 'row-click', row: Record<string, unknown>): void }>()

function keyOf(row: Record<string, unknown>, fallback: number): string | number {
  const value = row[props.rowKey] ?? row.id
  return (value as string | number) ?? fallback
}

function onRow(row: Record<string, unknown>): void {
  emit('row-click', row)
}
</script>

<template>
  <div class="aero-scroll overflow-x-auto">
    <table class="aero-table" :class="{ 'aero-table-clickable': clickable }">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="col.width ? { width: col.width } : undefined"
            :class="{ 'text-right': col.align === 'right', 'text-center': col.align === 'center' }"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <template v-if="loading">
          <tr v-for="n in skeletonRows" :key="`s${n}`">
            <td v-for="col in columns" :key="col.key">
              <span class="skeleton" :style="{ width: `${42 + ((n * 13 + col.key.length * 7) % 38)}%` }" />
            </td>
          </tr>
        </template>
        <template v-else>
          <tr
            v-for="(row, index) in rows"
            :key="keyOf(row, index)"
            :class="{ 'cursor-pointer': clickable }"
            @click="clickable && onRow(row)"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="{ mono: col.mono, 'text-right': col.align === 'right', 'text-center': col.align === 'center' }"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]" :index="index">
                {{ row[col.key] ?? '—' }}
              </slot>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length" class="!p-0">
              <slot name="empty">
                <AeroEmpty />
              </slot>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>
