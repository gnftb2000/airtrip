<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AeroToasts from '@/components/AeroToasts.vue'

const route = useRoute()

// The style tile is a design document: it owns the whole canvas.
const bare = computed(() => route.name === 'style-tile')

// Deterministic scene decoration: clouds and bubbles are positioned from a
// fixed table so the background is identical on every render.
const clouds = [
  { top: '8%', w: 340, h: 120, dur: 150, delay: -20, op: 0.9 },
  { top: '18%', w: 520, h: 160, dur: 200, delay: -90, op: 0.75 },
  { top: '4%', w: 220, h: 90, dur: 120, delay: -60, op: 0.6 },
  { top: '30%', w: 420, h: 130, dur: 240, delay: -150, op: 0.45 },
  { top: '22%', w: 260, h: 100, dur: 170, delay: -110, op: 0.55 },
  { top: '38%', w: 600, h: 150, dur: 300, delay: -40, op: 0.3 },
]

// Soft light shafts: cheap structure behind the glass, so the blur has something to chew on.
const shafts = [
  { left: '12%', w: 190, op: 0.5 },
  { left: '34%', w: 120, op: 0.35 },
  { left: '63%', w: 260, op: 0.42 },
]

// Big defocused light discs; they live behind the panels and give the blur a rim to bend.
const glares = [
  { left: '6%', top: '22%', size: 300, op: 0.6 },
  { left: '62%', top: '6%', size: 280, op: 0.55 },
  { left: '70%', top: '46%', size: 400, op: 0.5 },
  { left: '24%', top: '60%', size: 260, op: 0.42 },
]

const bubbles = [
  { left: '6%', size: 18, dur: 26, delay: -4 },
  { left: '14%', size: 9, dur: 20, delay: -11 },
  { left: '23%', size: 26, dur: 34, delay: -18 },
  { left: '31%', size: 12, dur: 23, delay: -7 },
  { left: '42%', size: 20, dur: 30, delay: -22 },
  { left: '53%', size: 8, dur: 18, delay: -3 },
  { left: '61%', size: 30, dur: 38, delay: -26 },
  { left: '70%', size: 14, dur: 24, delay: -14 },
  { left: '78%', size: 22, dur: 31, delay: -9 },
  { left: '88%', size: 11, dur: 21, delay: -17 },
  { left: '95%', size: 17, dur: 28, delay: -5 },
]
</script>

<template>
  <div class="relative min-h-screen">
    <div class="aero-scene">
      <div class="aero-sun" />
      <div
        v-for="(sh, i) in shafts"
        :key="`s${i}`"
        class="aero-shaft"
        :style="{ left: sh.left, width: `${sh.w}px`, opacity: sh.op }"
      />
      <div class="aero-hills" />
      <div
        v-for="(g, i) in glares"
        :key="`g${i}`"
        class="aero-glare"
        :style="{ left: g.left, top: g.top, width: `${g.size}px`, height: `${g.size}px`, opacity: g.op }"
      />
      <div
        v-for="(c, i) in clouds"
        :key="`c${i}`"
        class="aero-cloud"
        :style="{
          top: c.top,
          width: `${c.w}px`,
          height: `${c.h}px`,
          opacity: c.op,
          animationDuration: `${c.dur}s`,
          animationDelay: `${c.delay}s`,
        }"
      />
      <div
        v-for="(b, i) in bubbles"
        :key="`b${i}`"
        class="aero-bubble"
        :style="{
          left: b.left,
          width: `${b.size}px`,
          height: `${b.size}px`,
          animationDuration: `${b.dur}s`,
          animationDelay: `${b.delay}s`,
        }"
      />
    </div>

    <div v-if="bare" class="relative z-10 mx-auto w-full max-w-[1180px] px-5 py-7">
      <RouterView />
    </div>
    <div v-else class="relative z-10 mx-auto w-full max-w-[1320px] px-4 py-5 sm:px-5 sm:py-6">
      <RouterView />
    </div>

    <AeroToasts />
  </div>
</template>
