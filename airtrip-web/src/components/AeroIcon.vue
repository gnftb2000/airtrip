<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ name: string; size?: number; strokeWidth?: number }>(),
  { size: 16, strokeWidth: 1.6 },
)

// Hand-built glyph set: thin, geometric, no icon-font dependency.
const glyphs: Record<string, string> = {
  plane:
    '<path d="M3 11.2 21 4l-6.3 16.3-2.9-6.2-6.1-2.4Z" fill="currentColor" stroke="none"/><path d="m11.9 14.1 3.6-3.6" stroke="#ffffff" stroke-opacity=".85" stroke-width="1.1"/>',
  tower:
    '<path d="M12 2.8v3.2"/><path d="M9.4 6h5.2"/><path d="M10.2 6 8.6 21"/><path d="M13.8 6l1.6 15"/><path d="M7.5 21h9"/><path d="M10.6 11.5h2.8"/>',
  route:
    '<circle cx="5.5" cy="18.5" r="2.2"/><circle cx="18.5" cy="5.5" r="2.2"/><path d="M7.6 17.2c2.4-1.4 2.8-4.2 4.2-6.1 1.4-1.9 3-4 4.4-4.9" stroke-dasharray="2.4 2.2"/>',
  plan:
    '<path d="M9 4.5h6"/><path d="M8 4.5H6.2A1.2 1.2 0 0 0 5 5.7v13.6a1.2 1.2 0 0 0 1.2 1.2h11.6a1.2 1.2 0 0 0 1.2-1.2V5.7a1.2 1.2 0 0 0-1.2-1.2H16"/><path d="M8.6 11h6.8"/><path d="M8.6 15h4.4"/>',
  users:
    '<circle cx="9" cy="8.6" r="3.1"/><path d="M3.6 20c.5-3.2 2.7-4.9 5.4-4.9s4.9 1.7 5.4 4.9"/><path d="M15.6 6.2a3 3 0 0 1 0 4.8"/><path d="M17.4 15.6c1.6.6 2.6 2.1 2.9 4.4"/>',
  upload:
    '<path d="M12 16.2V4.6"/><path d="m8.2 8.4 3.8-3.8 3.8 3.8"/><path d="M5 15.2v3.2a1.2 1.2 0 0 0 1.2 1.2h11.6a1.2 1.2 0 0 0 1.2-1.2v-3.2"/>',
  gauge:
    '<rect x="4" y="4" width="6.4" height="6.4" rx="1.4"/><rect x="13.6" y="4" width="6.4" height="6.4" rx="1.4"/><rect x="4" y="13.6" width="6.4" height="6.4" rx="1.4"/><rect x="13.6" y="13.6" width="6.4" height="6.4" rx="1.4"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.2"/><path d="m15.4 15.4 4.1 4.1"/>',
  plus: '<path d="M12 5.6v12.8"/><path d="M5.6 12h12.8"/>',
  trash:
    '<path d="M4.6 6.6h14.8"/><path d="M9.4 6.6V4.8h5.2v1.8"/><path d="M6.8 6.6 7.7 20h8.6l.9-13.4"/><path d="M10.2 10.4v5.6"/><path d="M13.8 10.4v5.6"/>',
  download:
    '<path d="M12 4.6v11.6"/><path d="m8.2 12.4 3.8 3.8 3.8-3.8"/><path d="M5 16.6v2.2a1.2 1.2 0 0 0 1.2 1.2h11.6a1.2 1.2 0 0 0 1.2-1.2v-2.2"/>',
  globe:
    '<circle cx="12" cy="12" r="8.2"/><path d="M3.8 12h16.4"/><path d="M12 3.8c2.3 2.3 3.4 5.1 3.4 8.2s-1.1 5.9-3.4 8.2c-2.3-2.3-3.4-5.1-3.4-8.2s1.1-5.9 3.4-8.2Z"/>',
  sparkle:
    '<path d="M12 3.6l1.9 5 5 1.9-5 1.9-1.9 5-1.9-5-5-1.9 5-1.9 1.9-5Z" fill="currentColor" stroke="none"/>',
  check: '<path d="m5.4 12.6 4.2 4.2 9-9.6"/>',
  x: '<path d="m6.4 6.4 11.2 11.2"/><path d="m17.6 6.4-11.2 11.2"/>',
  'chevron-down': '<path d="m6.6 9.4 5.4 5.4 5.4-5.4"/>',
  'chevron-left': '<path d="m14.4 6.6-5.4 5.4 5.4 5.4"/>',
  'chevron-right': '<path d="m9.6 6.6 5.4 5.4-5.4 5.4"/>',
  calendar:
    '<rect x="4.2" y="5.6" width="15.6" height="14.4" rx="1.6"/><path d="M4.2 10h15.6"/><path d="M8.4 3.8v3.4"/><path d="M15.6 3.8v3.4"/>',
  refresh: '<path d="M19.4 12a7.4 7.4 0 1 1-2.2-5.2"/><path d="M19.8 4.4v4.4h-4.4"/>',
  filter: '<path d="M4 6h16"/><path d="M7 12h10"/><path d="M10 18h4"/>',
  logout:
    '<path d="M14.4 4.6H6.6A1.2 1.2 0 0 0 5.4 5.8v12.4a1.2 1.2 0 0 0 1.2 1.2h7.8"/><path d="M12.2 12h8"/><path d="m17.4 8.8 3.2 3.2-3.2 3.2"/>',
}

const glyph = computed(() => glyphs[props.name] ?? '')
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="glyph"
  />
</template>
