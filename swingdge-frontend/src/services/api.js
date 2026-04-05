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
    const isLoginEndpoint = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLoginEndpoint) {
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
  runScan: () => api.post('/scanner/run'),
  getResults: (date) => api.get('/scanner/results', { params: date ? { scan_date: date } : {} }),
  getHistory: () => api.get('/scanner/history'),
}

// ── Trade Plans (Phase 2) ─────────────────────────────────────────────────────
export const tradesApi = {
  getPlans: (status) => api.get('/trades/plans', { params: status ? { status } : {} }),
  getPlan: (id) => api.get(`/trades/plans/${id}`),
  generatePlan: (ticker, params) => api.get(`/trades/plans/generate/${ticker}`, { params }),
  createPlan: (data) => api.post('/trades/plans', data),
  updateStatus: (id, data) => api.patch(`/trades/plans/${id}/status`, data),
  updateNotes: (id, notes) => api.patch(`/trades/plans/${id}`, { notes }),
  cancelPlan: (id) => api.delete(`/trades/plans/${id}`),
  getHistory: () => api.get('/trades/history'),
}

// ── Settings (Phase 2) ───────────────────────────────────────────────────────
export const settingsApi = {
  getRules: () => api.get('/settings/rules'),
  updateRule: (key, value) => api.patch(`/settings/rules/${key}`, { rule_value: String(value) }),
}

// ── Alerts (Phase 4) ──────────────────────────────────────────────────────────
export const alertsApi = {
  getAlerts: () => api.get('/alerts'),
  sendTest: () => api.post('/alerts/test'),
}
