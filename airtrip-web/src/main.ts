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
const veil = Number(params.get('veil'))
if (Number.isFinite(veil)) {
  document.documentElement.style.setProperty('--veil', String(Math.min(Math.max(veil, 0), 2)))
}
const dim = Number(params.get('dim'))
if (Number.isFinite(dim) && dim > 0) {
  document.documentElement.style.setProperty('--glass-dim', String(Math.min(dim, 1)))
}

createApp(App).use(createPinia()).use(router).mount('#app')
