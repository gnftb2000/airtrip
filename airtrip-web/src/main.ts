import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/aero.css'
import './styles/theme-aqua.css'

// Temporary switch so any screen can be seen in the Aqua skin before the
// hard-coded colours are tokenised: ?theme=aqua (and ?wallpaper=on|off).
const params = new URLSearchParams(window.location.search)
const theme = params.get('theme')
if (theme === 'aqua') {
  document.documentElement.setAttribute('data-theme', 'aqua')
  const wallpaper = params.get('wallpaper')
  if (wallpaper === 'on') document.documentElement.setAttribute('data-wallpaper', 'on')
  if (wallpaper === 'off') document.documentElement.removeAttribute('data-wallpaper')
}

createApp(App).use(createPinia()).use(router).mount('#app')
