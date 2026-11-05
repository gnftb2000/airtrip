import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/aero.css'
import './styles/theme-aqua.css'

createApp(App).use(createPinia()).use(router).mount('#app')
