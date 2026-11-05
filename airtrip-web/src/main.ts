import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/aero.css'
import './styles/theme-aqua.css'

// Aqua is the default skin. `?theme=v0` shows the original blue build and
// `?bg=css` swaps the photographic wallpaper for the painted sky.
const params = new URLSearchParams(window.location.search)
if (params.get('theme') !== 'v0') {
  document.documentElement.setAttribute('data-theme', 'aqua')
  if (params.get('bg') !== 'css') document.documentElement.setAttribute('data-wallpaper', 'on')
}

// Live tuning: ?fill=0.15 sets the glass tint, ?dim=1 removes the backdrop
// dimming. Both land on <html> as inline custom properties, so they win over
// the stylesheet and work on every screen, not just the style tile.
const fill = Number(params.get('fill'))
if (Number.isFinite(fill) && fill > 0) {
  document.documentElement.style.setProperty('--glass-fill', `rgba(2, 28, 44, ${Math.min(fill, 1)})`)
}
// Note: Number(null) is 0, so presence has to be checked before parsing —
// otherwise the veil param defaults to "off" on every page.
const veilParam = params.get('veil')
if (veilParam !== null && Number.isFinite(Number(veilParam))) {
  const veil = Number(veilParam)
  // Scale the three veil alphas from here: calc() inside an rgba() alpha is not
  // reliable across engines, so the maths happens in JS instead.
  const k = Math.min(Math.max(veil, 0), 2)
  const root = document.documentElement.style
  root.setProperty('--veil-top', `rgba(2, 18, 30, ${(0.24 * k).toFixed(3)})`)
  root.setProperty('--veil-bottom', `rgba(2, 18, 30, ${(0.18 * k).toFixed(3)})`)
  root.setProperty('--veil-radial', `rgba(2, 20, 34, ${(0.16 * k).toFixed(3)})`)
  root.setProperty('--veil-radial-soft', `rgba(2, 20, 34, ${(0.05 * k).toFixed(3)})`)
}
const dim = Number(params.get('dim'))
if (Number.isFinite(dim) && dim > 0) {
  document.documentElement.style.setProperty('--glass-dim', String(Math.min(dim, 1)))
}

createApp(App).use(createPinia()).use(router).mount('#app')
