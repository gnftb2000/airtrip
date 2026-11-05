import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/',
      component: () => import('./layouts/AppShell.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('./pages/DashboardView.vue') },
        { path: 'airports', name: 'airports', component: () => import('./pages/AirportsView.vue') },
        {
          path: 'airports/:iata',
          name: 'airport',
          component: () => import('./pages/AirportDetailView.vue'),
        },
        { path: 'airlines', name: 'airlines', component: () => import('./pages/AirlinesView.vue') },
        {
          path: 'airlines/:iata',
          name: 'airline',
          component: () => import('./pages/AirlineDetailView.vue'),
        },
        { path: 'routes', name: 'routes', component: () => import('./pages/RoutesView.vue') },
        { path: 'plans', name: 'plans', component: () => import('./pages/PlansView.vue') },
        { path: 'plans/new', name: 'plan-new', component: () => import('./pages/PlanEditorView.vue') },
        {
          path: 'plans/:id/edit',
          name: 'plan-edit',
          component: () => import('./pages/PlanEditorView.vue'),
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('./pages/UsersView.vue'),
          meta: { admin: true },
        },
        {
          path: 'import',
          name: 'import',
          component: () => import('./pages/ImportView.vue'),
          meta: { admin: true },
        },
      ],
    },
    { path: '/login', name: 'login', component: () => import('./pages/LoginView.vue') },
    { path: '/style-tile', name: 'style-tile', component: () => import('./pages/StyleTile.vue') },
    {
      path: '/style-tile-aqua',
      name: 'style-tile-aqua',
      component: () => import('./pages/StyleTileAqua.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth || to.matched.some((record) => record.meta.requiresAuth)) {
    await auth.hydrate()
    if (!auth.token) {
      return { path: '/login', query: to.fullPath === '/' ? {} : { next: to.fullPath } }
    }
    if (!auth.account) {
      // Token exists but the session could not be restored.
      return { path: '/login' }
    }
    if (to.meta.admin && !auth.isAdmin) return { path: '/dashboard' }
  }

  return true
})

router.afterEach((to) => {
  const title = (to.name as string | undefined) ?? 'AirTrip'
  document.title = `AirTrip · ${title.charAt(0).toUpperCase()}${title.slice(1).replaceAll('-', ' ')}`
})

export default router
