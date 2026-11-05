<script setup lang="ts">
import AeroWindow from '@/components/AeroWindow.vue'
import AeroButton from '@/components/AeroButton.vue'
import AeroIcon from '@/components/AeroIcon.vue'

const palette = [
  { name: 'Sky high', hex: '#7ED2FA', ink: '#0A3A55' },
  { name: 'Sky mid', hex: '#3FB4EC', ink: '#0A3A55' },
  { name: 'Sky deep', hex: '#1489CC', ink: '#ffffff' },
  { name: 'Aero blue', hex: '#1F9AD9', ink: '#ffffff' },
  { name: 'Aqua', hex: '#57E0D2', ink: '#0A3A55' },
  { name: 'Aqua deep', hex: '#17A89B', ink: '#ffffff' },
  { name: 'Lime', hex: '#9AE86F', ink: '#224d14' },
  { name: 'Grass', hex: '#56B23F', ink: '#ffffff' },
  { name: 'Sun', hex: '#FFF6CF', ink: '#0A3A55' },
  { name: 'Ink', hex: '#0A3A55', ink: '#ffffff' },
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
        <div class="text-[19px] font-normal tracking-[0.3px] text-[color:var(--ink)] [text-shadow:0_1px_0_rgba(255,255,255,0.85)]">
          AirTrip
        </div>
        <div class="text-[11.5px] font-light tracking-[0.6px] text-[color:var(--ink-soft)]">Flight network explorer</div>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <span class="badge"><AeroIcon name="sparkle" :size="11" /> style tile · v0</span>
        <AeroButton variant="glass" size="sm"><AeroIcon name="users" :size="13" /> Sign in</AeroButton>
      </div>
    </div>

    <!-- hero -->
    <AeroWindow title="AirTrip — flight network explorer" subtitle="Design language · Frutiger Aero / Web 2.0 Gloss">
      <div class="grid gap-6 md:grid-cols-[1.35fr_1fr] md:items-center">
        <div>
          <h1 class="m-0 text-[38px] leading-[1.1] font-light tracking-[-0.5px] text-[color:var(--ink)] [text-shadow:0_1px_0_rgba(255,255,255,0.9)]">
            Bright air, wet glass,<br /><span class="text-[#1272a8]">honest data.</span>
          </h1>
          <p class="mt-3 max-w-[46ch] text-[13.5px] leading-[1.65] font-light text-[color:var(--ink-soft)]">
            A visual language for the AirTrip API: glossy hard-stop gradients, one-pixel highlights,
            real reflections and a sky that keeps moving. Everything is drawn with CSS and SVG — no
            wallpapers, no stock art, nothing to license.
          </p>
          <div class="mt-5 flex flex-wrap items-center gap-2.5">
            <AeroButton size="lg"><AeroIcon name="search" :size="15" /> Explore airports</AeroButton>
            <AeroButton variant="glass" size="lg"><AeroIcon name="plan" :size="15" /> Plan a trip</AeroButton>
          </div>
        </div>

        <div class="flex items-end justify-center gap-4">
          <div class="orb sweep reflect" style="width: 96px; height: 96px">
            <AeroIcon name="plane" :size="46" />
          </div>
        </div>
      </div>
    </AeroWindow>

    <!-- palette -->
    <AeroWindow title="Palette" subtitle="sky · aqua · nature · ink">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div
          v-for="c in palette"
          :key="c.hex"
          class="rounded-[8px] border border-white/80 p-3 shadow-[inset_0_1px_0_#fff,0_3px_8px_-4px_rgba(9,60,94,0.5)]"
          :style="{ background: c.hex, color: c.ink }"
        >
          <div class="text-[12.5px] font-normal">{{ c.name }}</div>
          <div class="mono mt-1 opacity-80" :style="{ color: c.ink }">{{ c.hex }}</div>
        </div>
      </div>
    </AeroWindow>

    <div class="grid gap-5 lg:grid-cols-2">
      <!-- type -->
      <AeroWindow title="Type" subtitle="Segoe UI / Tahoma · light weights only">
        <div class="space-y-3">
          <div class="text-[32px] leading-tight font-light tracking-[-0.4px] text-[color:var(--ink)]">Display 32 / 300</div>
          <div class="text-[22px] leading-tight font-light text-[color:var(--ink)]">Heading 22 / 300</div>
          <div class="text-[15px] font-normal text-[color:var(--ink)]">Subheading 15 / 400</div>
          <div class="text-[13.5px] leading-[1.65] font-light text-[color:var(--ink-soft)]">
            Body 13.5 / 300 — the workhorse. Long form stays readable on glass because contrast is
            pushed with ink instead of weight.
          </div>
          <div class="text-[11px] font-normal tracking-[0.14em] text-[color:var(--ink-soft)] uppercase">
            Label 11 / 400 · tracked 0.14em
          </div>
          <div class="mono">SYD → MEL · QF 401 · 0 stops</div>
        </div>
      </AeroWindow>

      <!-- badges + stats -->
      <AeroWindow title="Status & counters" subtitle="badges, stats, orbs">
        <div class="mb-4 flex flex-wrap gap-2">
          <span class="badge"><AeroIcon name="check" :size="11" /> active</span>
          <span class="badge badge-aqua"><AeroIcon name="route" :size="11" /> direct</span>
          <span class="badge badge-lime"><AeroIcon name="sparkle" :size="11" /> new</span>
          <span class="badge"><AeroIcon name="x" :size="11" /> archived</span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div v-for="s in stats" :key="s.label" class="tile reflect-tile reflect-lg flex items-center gap-3">
            <div class="orb" :class="s.tone" style="width: 34px; height: 34px">
              <AeroIcon :name="s.icon" :size="17" />
            </div>
            <div>
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </AeroWindow>
    </div>

    <!-- controls -->
    <AeroWindow title="Controls" subtitle="buttons · fields · toggles">
      <div class="grid gap-6 md:grid-cols-2">
        <div class="space-y-4">
          <div class="flex flex-wrap items-center gap-2.5">
            <AeroButton>Primary</AeroButton>
            <AeroButton variant="glass">Glass</AeroButton>
            <AeroButton variant="aqua">Aqua</AeroButton>
            <AeroButton variant="danger"><AeroIcon name="trash" :size="13" /> Delete</AeroButton>
          </div>
          <div class="flex flex-wrap items-center gap-2.5">
            <AeroButton size="sm">Small</AeroButton>
            <AeroButton size="lg">Large</AeroButton>
            <AeroButton icon-only variant="glass"><AeroIcon name="refresh" :size="15" /></AeroButton>
            <AeroButton disabled>Disabled</AeroButton>
          </div>
          <div>
            <label class="field-label">Search airports</label>
            <div class="relative">
              <span class="absolute top-1/2 left-3 -translate-y-1/2 text-[#2e88b8]">
                <AeroIcon name="search" :size="14" />
              </span>
              <input class="field pl-9" value="Sydney" />
            </div>
            <div class="field-hint">Try <em>fuzzy</em> matching: “Sydny” still finds SYD.</div>
          </div>
        </div>

        <div class="space-y-4">
          <div>
            <label class="field-label">Airline</label>
            <div class="select-wrap">
              <select class="field">
                <option>Qantas (QF)</option>
                <option>Virgin Australia (VA)</option>
              </select>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="field-label">Origin</label>
              <input class="field mono" value="SYD" />
            </div>
            <div>
              <label class="field-label">Destination</label>
              <input class="field mono" value="MEL" />
            </div>
          </div>
          <div class="flex items-center justify-between rounded-[8px] border border-white/80 bg-white/40 px-3 py-2.5">
            <div class="text-[13px] font-light text-[color:var(--ink)]">Fuzzy matching</div>
            <div class="switch" role="switch" aria-checked="true" aria-label="Fuzzy matching">
              <span class="switch-knob" />
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <AeroButton variant="glass" size="sm">Reset</AeroButton>
            <AeroButton size="sm"><AeroIcon name="check" :size="13" /> Apply</AeroButton>
          </div>
        </div>
      </div>
    </AeroWindow>

    <!-- table -->
    <AeroWindow title="Airports" subtitle="46 records · page 1 of 10" :padded="false">
      <template #actions>
        <span class="badge badge-aqua">live</span>
      </template>
      <div class="aero-scroll overflow-x-auto p-4">
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
              <td><span class="mono">{{ a.iata }}</span></td>
              <td>{{ a.name }}</td>
              <td>{{ a.city }}</td>
              <td>{{ a.country }}</td>
              <td class="text-right">{{ a.airlines }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <div class="text-[12px] font-light text-[color:var(--ink-soft)]">Showing 1–5 of 46</div>
        <div class="ml-auto flex items-center gap-1.5">
          <AeroButton variant="glass" size="sm" icon-only><AeroIcon name="chevron-left" :size="14" /></AeroButton>
          <AeroButton size="sm">1</AeroButton>
          <AeroButton variant="glass" size="sm">2</AeroButton>
          <AeroButton variant="glass" size="sm">3</AeroButton>
          <AeroButton variant="glass" size="sm" icon-only><AeroIcon name="chevron-right" :size="14" /></AeroButton>
        </div>
      </template>
    </AeroWindow>

    <!-- windows + dialog -->
    <div class="grid gap-5 lg:grid-cols-2">
      <AeroWindow variant="dark" title="Dark glass" subtitle="for dense data and night states">
        <p class="m-0 text-[13px] leading-[1.65] font-light text-[color:var(--ink-on-dark)]">
          Same chrome, inverted fill. Used sparingly: route detail drawers, import logs, the confirm
          dialog. Never as a full-page background.
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <AeroButton size="sm">Confirm</AeroButton>
          <AeroButton variant="glass" size="sm">Cancel</AeroButton>
        </div>
      </AeroWindow>

      <AeroWindow title="Dialog" subtitle="destructive action · 409 protected">
        <div class="rounded-[10px] border border-white/70 bg-white/55 p-4">
          <div class="flex items-start gap-3">
            <div class="orb" style="width: 34px; height: 34px; background: radial-gradient(circle at 32% 26%, #fff 0%, #ffe1e1 18%, #f78d8d 46%, #d63c3c 72%, #941e1e 100%)">
              <AeroIcon name="trash" :size="16" />
            </div>
            <div>
              <div class="text-[14px] font-normal text-[color:var(--ink)]">Delete “Winter loop”?</div>
              <div class="mt-1 text-[12.5px] leading-[1.6] font-light text-[color:var(--ink-soft)]">
                A plan that still has routes returns <span class="mono">409</span>. Remove its routes first,
                or the request is rejected.
              </div>
            </div>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <AeroButton variant="glass" size="sm">Keep it</AeroButton>
            <AeroButton variant="danger" size="sm">Delete plan</AeroButton>
          </div>
        </div>
      </AeroWindow>
    </div>

    <!-- icons -->
    <AeroWindow title="Icons" subtitle="hand-drawn SVG glyphs · 1.6px stroke · inherit currentColor">
      <div class="flex flex-wrap gap-2">
        <div
          v-for="name in icons"
          :key="name"
          class="flex w-[76px] flex-col items-center gap-1.5 rounded-[8px] border border-white/70 bg-white/35 px-2 py-2.5"
        >
          <AeroIcon :name="name" :size="20" class="text-[color:var(--ink-soft)]" />
          <span class="text-[10px] font-light tracking-[0.3px] text-[color:var(--ink-soft)]">{{ name }}</span>
        </div>
      </div>
    </AeroWindow>

    <!-- rules -->
    <AeroWindow title="Rules of the look" subtitle="what keeps this from becoming 2007 clip-art">
      <div class="grid gap-5 md:grid-cols-2">
        <div>
          <div class="field-label">Do</div>
          <ul class="m-0 list-none space-y-1.5 p-0 text-[13px] leading-[1.6] font-light text-[color:var(--ink)]">
            <li>Hard-stop gradients (52/48), one white gloss band on top.</li>
            <li>1px bright inner rim + soft outer shadow = glass, not haze.</li>
            <li>Blur only reads as glass when there is structure behind it; flat sky stays flat.</li>
            <li>Text in ink on light glass; never white on white.</li>
            <li>One moving layer behind the content: sky, clouds, bubbles.</li>
          </ul>
        </div>
        <div>
          <div class="field-label">Don't</div>
          <ul class="m-0 list-none space-y-1.5 p-0 text-[13px] leading-[1.6] font-light text-[color:var(--ink)]">
            <li>Drop shadows on text; use 1px white light instead.</li>
            <li>Three glass layers stacked — soup. Dense data gets a denser pane.</li>
            <li>Saturated green as a surface colour; it stays an accent.</li>
            <li>Bold weights. 300/400 only, tracking does the work.</li>
            <li>Reflections on tier-one objects only: hero orb, counter tiles. Never on grids.</li>
          </ul>
        </div>
      </div>
    </AeroWindow>

    <div class="pb-2 text-center text-[11px] font-light tracking-[0.4px] text-[#2a6382]">
      AirTrip design language v0 · CSS + SVG only · no external assets
    </div>
  </div>
</template>

<style scoped>
.switch {
  position: relative;
  width: 42px;
  height: 22px;
  border-radius: 999px;
  background: linear-gradient(180deg, #bff2e9 0%, #4dd8c4 52%, #16a291 52%, #0b7f72 100%);
  border: 1px solid #0b7f72;
  box-shadow: inset 0 1px 3px rgba(0, 40, 36, 0.35), 0 1px 0 rgba(255, 255, 255, 0.8);
  cursor: pointer;
}

.switch::before {
  content: '';
  position: absolute;
  left: 3px;
  right: 4px;
  top: 2px;
  height: 44%;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.05));
}

.switch-knob {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: radial-gradient(circle at 34% 28%, #fff 0%, #f4fdff 40%, #d7eef9 70%, #b4dcee 100%);
  border: 1px solid rgba(11, 95, 150, 0.55);
  box-shadow: 0 1px 2px rgba(6, 50, 76, 0.35);
}
</style>
