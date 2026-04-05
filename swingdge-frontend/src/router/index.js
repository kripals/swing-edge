import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('../views/Portfolio.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/scanner',
    name: 'Scanner',
    component: () => import('../views/Scanner.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/plan',
    name: 'TradePlanGenerate',
    component: () => import('../views/TradePlan.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/trades/:id',
    name: 'TradePlan',
    component: () => import('../views/TradePlan.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('../views/Market.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/history',
    name: 'TradeHistory',
    component: () => import('../views/TradeHistory.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Auth guard
router.beforeEach((to) => {
  const token = localStorage.getItem('swingdge_token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'Login' }
  }
  if (to.name === 'Login' && token) {
    return { name: 'Dashboard' }
  }
})

export default router
