import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 90_000, // 90s — allows for Render cold start (~60s) + processing time
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('swingdge_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 — clear token and redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('swingdge_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (password) => api.post('/auth/login', { password }),
}

// ── Portfolio ─────────────────────────────────────────────────────────────────
export const portfolioApi = {
  getSummary: () => api.get('/portfolio/summary'),
  getHoldings: () => api.get('/portfolio/holdings'),
  getAccounts: () => api.get('/portfolio/accounts'),
  addHolding: (data) => api.post('/portfolio/holdings', data),
}

// ── Market (Phase 3) ─────────────────────────────────────────────────────────
export const marketApi = {
  getQuote: (ticker) => api.get(`/market/quote/${ticker}`),
  getSectors: () => api.get('/market/sectors'),
  getMacro: () => api.get('/market/macro'),
}

// ── Scanner (Phase 2) ─────────────────────────────────────────────────────────
export const scannerApi = {
  runScan: () => api.get('/scanner/run'),
  getResults: () => api.get('/scanner/results'),
}

// ── Trade Plans (Phase 2) ─────────────────────────────────────────────────────
export const tradesApi = {
  getPlans: () => api.get('/trades/plans'),
  createPlan: (data) => api.post('/trades/plans', data),
  updatePlan: (id, data) => api.patch(`/trades/plans/${id}`, data),
  getHistory: () => api.get('/trades/history'),
}

// ── Alerts (Phase 4) ──────────────────────────────────────────────────────────
export const alertsApi = {
  getAlerts: () => api.get('/alerts'),
  sendTest: () => api.post('/alerts/test'),
}
