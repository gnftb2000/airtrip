<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AeroWindow from '@/components/AeroWindow.vue'
import AeroButton from '@/components/AeroButton.vue'
import AeroIcon from '@/components/AeroIcon.vue'

// The theme is a document-level switch so the shared background scene
// re-skins itself; the previous value is restored when the page unmounts.
let previous: string | null = null

// Swap between the painted CSS sky and the photographic wallpaper.
// ?fill=0.38 overrides the glass alpha on the fly, so the mix can be tuned
// without editing the stylesheet (?bg=css renders the painted sky instead).
const fillParam = Number(new URLSearchParams(window.location.search).get('fill'))
const glassFill = Number.isFinite(fillParam) && fillParam > 0 ? Math.min(fillParam, 1) : null

// ?bg=css renders the painted sky, default is the photographic wallpaper
const wallpaper = ref(new URLSearchParams(window.location.search).get('bg') !== 'css')
const root = () => document.documentElement

watch(wallpaper, (on) => {
  if (on) root().setAttribute('data-wallpaper', 'on')
  else root().removeAttribute('data-wallpaper')
})

onMounted(() => {
  previous = root().getAttribute('data-theme')
  root().setAttribute('data-theme', 'aqua')
  if (wallpaper.value) root().setAttribute('data-wallpaper', 'on')
  if (glassFill !== null) root().style.setProperty('--glass-fill', `rgba(4, 40, 58, ${glassFill})`)
})
onBeforeUnmount(() => {
  if (previous) root().setAttribute('data-theme', previous)
  else root().removeAttribute('data-theme')
  root().removeAttribute('data-wallpaper')
  root().style.removeProperty('--glass-fill')
})

// The page header sits straight on the scene, so its ink flips on the photo.
const brandInk = '#ffffff'
const brandShadow = '0 2px 6px rgba(0, 20, 42, 0.6)'
const brandSub = 'rgba(255, 255, 255, 0.88)'

const palette = [
  { name: 'Sky high', hex: '#A6F2FF', ink: '#053a4c' },
  { name: 'Sky mid', hex: '#3FD9F2', ink: '#053a4c' },
  { name: 'Aqua', hex: '#25E0E6', ink: '#053a4c' },
  { name: 'Aero blue', hex: '#1CB6E0', ink: '#ffffff' },
  { name: 'Teal deep', hex: '#0E96B0', ink: '#ffffff' },
  { name: 'Grass', hex: '#4FB45F', ink: '#ffffff' },
  { name: 'Lime', hex: '#A8F07A', ink: '#1c4a12' },
  { name: 'Sun', hex: '#FFFFCB', ink: '#053a4c' },
  { name: 'Ink', hex: '#053A4C', ink: '#ffffff' },
  { name: 'Glass tint', hex: '#F2FEFF', ink: '#053a4c' },
]

const airports = [
  { iata: 'SYD', name: 'Sydney Kingsford Smith', city: 'Sydney', country: 'Australia', airlines: 9 },
  { iata: 'MEL', name: 'Melbourne Tullamarine', city: 'Melbourne', country: 'Australia', airlines: 7 },
  { iata: 'LAX', name: 'Los Angeles International', city: 'Los Angeles', country: 'United States', airlines: 6 },
  { iata: 'LHR', name: 'London Heathrow', city: 'London', country: 'United Kingdom', airlines: 8 },
  { iata: 'NRT', name: 'Tokyo Narita', city: 'Tokyo', country: 'Japan', airlines: 5 },
]

const stats = [
  { label: 'Airports', value: '46', icon: 'tower', tone: '' },
  { label: 'Airlines', value: '15', icon: 'globe', tone: 'orb-aqua' },
  { label: 'Routes', value: '260', icon: 'route', tone: 'orb-lime' },
  { label: 'My plans', value: '3', icon: 'plan', tone: '' },
]

const icons = ['plane', 'tower', 'route', 'plan', 'users', 'upload', 'gauge', 'search', 'calendar', 'globe', 'download', 'logout']
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- brand strip -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="orb orb-lg sweep"><AeroIcon name="plane" :size="26" /></div>
      <div>
        <div
          class="text-[19px] font-normal tracking-[0.3px]"
          :style="{ color: brandInk, textShadow: brandShadow }"
        >
          AirTrip
        </div>
        <div class="text-[11.5px] font-light tracking-[0.6px]" :style="{ color: brandSub }">
          Flight network explorer
        </div>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <span class="badge whitespace-nowrap"><AeroIcon name="sparkle" :size="11" /> style tile · v2 aqua</span>
        <button
          type="button"
          class="badge whitespace-nowrap"
          :style="{ borderColor: wallpaper ? '#ffffff' : 'rgba(255,255,255,0.6)', opacity: wallpaper ? 1 : 0.75 }"
          @click="wallpaper = true"
        >
          <AeroIcon name="globe" :size="11" /> wallpaper
        </button>
        <button
          type="button"
          class="badge whitespace-nowrap"
          :style="{ borderColor: wallpaper ? 'rgba(255,255,255,0.6)' : '#ffffff', opacity: wallpaper ? 0.75 : 1 }"
          @click="wallpaper = false"
        >
          <AeroIcon name="sparkle" :size="11" /> CSS sky
        </button>
        <RouterLink to="/style-tile" class="badge whitespace-nowrap" style="text-decoration: none">
          <AeroIcon name="chevron-left" :size="11" /> v0
        </RouterLink>
      </div>
    </div>

    <!-- hero -->
    <AeroWindow title="AirTrip — aqua skin" subtitle="Style tile v2 · white edges, cyan glow, 8px glass">
      <div class="grid gap-6 md:grid-cols-[1.35fr_1fr] md:items-center">
        <div>
          <h1 class="t-display m-0 text-[38px] leading-[1.1] font-light tracking-[-0.5px]">
            Wet turquoise,<br /><span class="t-accent">white edge.</span>
          </h1>
          <p class="t-body mt-3 mb-0 max-w-[46ch] text-[13.5px] leading-[1.65] font-light">
            The same panes and tables, re-cut in the Aqua recipe: every glass surface gets a
            1.5&nbsp;px pure-white edge, an inner cyan glow and a wider blur, controls turn into
            white pills, and the scene drops to a turquoise sky over a painted grass horizon.
          </p>
          <div class="mt-5 flex flex-wrap gap-2.5">
            <AeroButton><AeroIcon name="search" :size="14" /> Explore airports</AeroButton>
            <AeroButton variant="glass"><AeroIcon name="plan" :size="14" /> Plan a trip</AeroButton>
            <AeroButton variant="aqua"><AeroIcon name="sparkle" :size="14" /> Aqua accent</AeroButton>
          </div>
        </div>
        <div class="relative flex min-h-[190px] items-center justify-center">
          <div class="orb orb-lg sweep reflect-lg" style="width: 118px; height: 118px"><AeroIcon name="plane" :size="40" /></div>
        </div>
      </div>
    </AeroWindow>

    <!-- palette -->
    <AeroWindow title="Palette" subtitle="turquoise · aqua · grass · ink">
      <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        <div
          v-for="c in palette"
          :key="c.name"
          class="rounded-[8px] border px-3 py-2.5"
          :style="{
            background: c.hex,
            borderColor: 'rgba(255,255,255,0.9)',
            boxShadow: 'inset 0 0 12px rgba(148,246,255,0.45), 0 4px 10px -8px rgba(3,45,60,0.5)',
            color: c.ink,
          }"
        >
          <div class="text-[11px] tracking-[0.3px] opacity-80">{{ c.name }}</div>
          <div class="swatch-mono mono text-[12px]">{{ c.hex }}</div>
        </div>
      </div>
    </AeroWindow>

    <div class="grid gap-5 lg:grid-cols-[1.05fr_1fr]">
      <!-- type -->
      <AeroWindow title="Type" subtitle="Segoe UI / Inter · light weights only">
        <div class="t-display text-[32px] leading-[1.1] font-light">Display 32 / 300</div>
        <div class="t-ink mt-1 text-[22px] font-light">Heading 22 / 300</div>
        <div class="t-ink mt-1 text-[15px]">Subheading 15 / 400</div>
        <p class="t-body mt-2 max-w-[52ch] text-[13.5px] leading-[1.65] font-light">
          Body 13.5 / 300 — white edges buy contrast, so long form can stay light. Numbers and
          codes keep tabular figures so columns line up.
        </p>
        <div class="t-label mt-2 text-[11px] tracking-[0.14em]">LABEL 11 / 400 · TRACKED 0.14EM</div>
        <div class="t-mono mt-1.5 mono text-[12.5px]">SYD → MEL · QF 401 · 0 stops</div>
      </AeroWindow>

      <!-- status -->
      <AeroWindow title="Status & counters" subtitle="badges, stats, orbs">
        <div class="flex flex-wrap gap-1.5">
          <span class="badge"><AeroIcon name="check" :size="10" /> active</span>
          <span class="badge badge-aqua"><AeroIcon name="sparkle" :size="10" /> aqua</span>
          <span class="badge badge-lime"><AeroIcon name="sparkle" :size="10" /> new</span>
          <span class="badge badge-mono"><AeroIcon name="x" :size="10" /> archived</span>
        </div>
        <div class="mt-3 grid grid-cols-2 gap-2.5">
          <div v-for="s in stats" :key="s.label" class="tile flex items-center gap-3">
            <div class="orb" :class="s.tone"><AeroIcon :name="s.icon" :size="15" /></div>
            <div class="min-w-0">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </AeroWindow>
    </div>

    <!-- controls -->
    <AeroWindow title="Controls" subtitle="buttons · fields · toggles">
      <div class="grid gap-5 md:grid-cols-[1fr_1fr]">
        <div class="flex flex-wrap items-center gap-2">
          <AeroButton>Primary</AeroButton>
          <AeroButton variant="glass">Glass</AeroButton>
          <AeroButton variant="aqua">Aqua</AeroButton>
          <AeroButton variant="danger"><AeroIcon name="trash" :size="13" /> Delete</AeroButton>
          <AeroButton size="sm">Small</AeroButton>
          <AeroButton size="lg">Large</AeroButton>
          <AeroButton variant="glass" iconOnly aria-label="Refresh"><AeroIcon name="refresh" :size="14" /></AeroButton>
          <AeroButton disabled>Disabled</AeroButton>
        </div>
        <div class="grid gap-3">
          <label class="block">
            <span class="field-label">Airline</span>
            <div class="select-wrap">
              <select class="field">
                <option>Qantas (QF)</option>
                <option>Virgin Australia (VA)</option>
              </select>
            </div>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="field-label">Origin</span>
              <input class="field" value="SYD" />
            </label>
            <label class="block">
              <span class="field-label">Destination</span>
              <input class="field" value="MEL" />
            </label>
          </div>
          <div class="t-ink flex items-center gap-2 text-[13px]">
            <input id="fuzzy-aqua" class="checkbox" type="checkbox" checked />
            <label for="fuzzy-aqua">Fuzzy matching</label>
          </div>
        </div>
      </div>
    </AeroWindow>

    <!-- table -->
    <AeroWindow title="Airports" subtitle="46 records · page 1 of 10" dense>
      <template #actions>
        <span class="badge badge-lime"><AeroIcon name="check" :size="10" /> live</span>
      </template>
      <div class="aero-scroll overflow-x-auto">
        <table class="aero-table">
          <thead>
            <tr>
              <th>IATA</th>
              <th>Airport</th>
              <th>City</th>
              <th>Country</th>
              <th class="text-right">Airlines</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in airports" :key="a.iata">
              <td><span class="badge badge-mono">{{ a.iata }}</span></td>
              <td>{{ a.name }}</td>
              <td>{{ a.city }}</td>
              <td>{{ a.country }}</td>
              <td class="text-right">{{ a.airlines }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </AeroWindow>

    <div class="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
      <!-- dark glass -->
      <AeroWindow title="Dark glass" subtitle="for dense data and night states" variant="dark">
        <p class="m-0 max-w-[42ch] text-[13.5px] leading-[1.65] font-light text-[#d7f7ff]">
          Same chrome, inverted fill. Used sparingly: route detail drawers, import logs, the
          confirm dialog. Never as a full-page background.
        </p>
        <div class="mt-3 flex gap-2">
          <AeroButton variant="aqua" size="sm">Confirm</AeroButton>
          <AeroButton variant="glass" size="sm">Cancel</AeroButton>
        </div>
      </AeroWindow>

      <!-- dialog -->
      <AeroWindow title="Dialog" subtitle="destructive action · 409 protected">
        <div class="aqua-inset rounded-[10px] border border-white/60 p-4">
          <div class="flex items-start gap-3">
            <div class="orb orb-lg"><AeroIcon name="trash" :size="16" /></div>
            <div class="min-w-0">
              <div class="t-ink text-[14.5px]">Delete “Winter loop”?</div>
              <p class="t-body mt-1 mb-0 text-[13px] leading-[1.6] font-light">
                A plan that still has routes returns 409. Remove its routes first, or the request is
                rejected.
              </p>
            </div>
          </div>
          <div class="mt-3 flex justify-end gap-2">
            <AeroButton variant="glass" size="sm">Keep it</AeroButton>
            <AeroButton variant="danger" size="sm"><AeroIcon name="trash" :size="12" /> Delete plan</AeroButton>
          </div>
        </div>
      </AeroWindow>
    </div>

    <!-- icons -->
    <AeroWindow title="Icons" subtitle="hand-drawn SVG glyphs · 1.6px stroke · inherit currentColor">
      <div class="flex flex-wrap gap-2">
        <div
          v-for="i in icons"
          :key="i"
          class="tile flex w-[72px] flex-col items-center gap-1.5 px-2 py-2.5"
        >
          <AeroIcon :name="i" :size="18" />
          <span class="t-label text-[10.5px] tracking-[0.3px]">{{ i }}</span>
        </div>
      </div>
    </AeroWindow>

    <!-- rules -->
    <AeroWindow title="Rules of the aqua skin" subtitle="what changed vs v0">
      <div class="t-body grid gap-4 text-[13px] leading-[1.6] font-light md:grid-cols-2">
        <div>
          <div class="t-label mb-1.5 text-[11px] tracking-[0.14em]">DO</div>
          <ul class="m-0 grid list-none gap-1.5 p-0">
            <li>1.5 px pure-white edge on every pane, tile, field and badge.</li>
            <li>Inner cyan glow <span class="mono">inset 0 0 20px #94f6ff66</span> instead of a dark rim.</li>
            <li>Body type is white at 300 weight with a 1 px dark shadow; the glass holds it at 46% ink.</li>
            <li>Glass reads at <span class="mono">blur(8px) saturate(150%)</span> — wider than v0, so edges stay soft.</li>
            <li>Controls are 45 px pills; only fields keep an 8 px radius.</li>
            <li>Sky is turquoise with a painted grass horizon; no photographic wallpaper.</li>
          </ul>
        </div>
        <div>
          <div class="t-label mb-1.5 text-[11px] tracking-[0.14em]">DON'T</div>
          <ul class="m-0 grid list-none gap-1.5 p-0">
            <li>Copy their wallpapers, icon packs or mascot — the site says it does not own them.</li>
            <li>Put the glossy row-card treatment on data tables; they go muddy fast.</li>
            <li>Stack more than two glass layers; white edges multiply into mush.</li>
            <li>Put white type on the pale chrome — bars, buttons and fields keep dark ink.</li>
            <li>Animate the glow — it cheapens the material.</li>
          </ul>
        </div>
      </div>
    </AeroWindow>

    <div class="t-label pb-2 text-center text-[11.5px] tracking-[0.5px]">
      AirTrip · aqua skin v2 · CSS + SVG only · no external assets
    </div>
  </div>
</template>
