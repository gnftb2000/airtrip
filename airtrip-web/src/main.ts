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

createApp(App).use(createPinia()).use(router).mount('#app')
