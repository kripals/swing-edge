import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { portfolioApi } from '../services/api'

export const usePortfolioStore = defineStore('portfolio', () => {
  const summary = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const isColdStart = ref(false)

  const totalValueCad = computed(() => summary.value?.total_value_cad ?? 0)
  const totalPnl = computed(() => summary.value?.total_unrealized_pnl ?? 0)
  const totalPnlPct = computed(() => summary.value?.total_unrealized_pnl_pct ?? 0)
  const accounts = computed(() => summary.value?.accounts ?? [])
  const flags = computed(() => summary.value?.flags ?? [])
  const sectorWeights = computed(() => summary.value?.sector_weights ?? {})

  const allHoldings = computed(() => {
    return accounts.value.flatMap(acc => acc.holdings)
  })

  const problemHoldings = computed(() => {
    return allHoldings.value.filter(h =>
      h.flags.includes('LARGE_LOSS') ||
      h.flags.includes('LEVERAGED_ETF')
    )
  })

  async function fetchSummary() {
    loading.value = true
    error.value = null
    try {
      const resp = await portfolioApi.getSummary()
      summary.value = resp.data
      // Check if this was a cold start
      isColdStart.value = resp.headers['x-cold-start'] === 'true'
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load portfolio'
    } finally {
      loading.value = false
    }
  }

  function formatCad(value) {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD',
      minimumFractionDigits: 2,
    }).format(value)
  }

  function formatPct(value) {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  return {
    summary, loading, error, isColdStart,
    totalValueCad, totalPnl, totalPnlPct,
    accounts, flags, sectorWeights,
    allHoldings, problemHoldings,
    fetchSummary, formatCad, formatPct,
  }
})
