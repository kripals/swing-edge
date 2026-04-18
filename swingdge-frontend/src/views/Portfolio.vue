<template>
  <div class="portfolio-page">
    <div v-if="store.loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <template v-else-if="store.summary">
      <!-- Page header -->
      <div class="page-header">
        <div>
          <h1 class="page-title">Portfolio</h1>
          <p class="page-sub">{{ store.formatCad(store.totalValueCad) }} total · {{ store.formatPct(store.totalPnlPct) }} unrealized</p>
        </div>
        <button @click="store.fetchSummary()" class="refresh-btn">Refresh</button>
      </div>

      <!-- Flags -->
      <div v-if="store.flags.length" class="flags-row">
        <div v-for="flag in store.flags" :key="flag" class="flag">{{ formatFlag(flag) }}</div>
      </div>

      <!-- Per-account sections -->
      <div v-for="account in store.accounts" :key="account.id" class="account-section">
        <div class="account-header">
          <div>
            <h2 class="account-name">{{ account.name }}</h2>
            <span class="account-meta">{{ account.account_type }} · {{ store.formatCad(account.total_market_value_cad) }}</span>
          </div>
          <div class="account-pnl" :class="account.total_unrealized_pnl >= 0 ? 'positive' : 'negative'">
            {{ store.formatCad(account.total_unrealized_pnl) }}
            <span class="pct">({{ store.formatPct(account.total_unrealized_pnl_pct) }})</span>
          </div>
        </div>

        <div class="holdings-grid">
          <HoldingCard
            v-for="holding in account.holdings"
            :key="holding.id"
            :holding="holding"
          />
        </div>
      </div>

      <!-- Advisor Panel -->
      <div class="advisor-panel">
        <div class="advisor-header">
          <div class="advisor-title">
            Portfolio Advisor
            <span class="advisor-badge sell" v-if="advisorSellCount > 0">{{ advisorSellCount }} SELL</span>
            <span class="advisor-badge watch" v-if="advisorWatchCount > 0">{{ advisorWatchCount }} WATCH</span>
          </div>
          <div class="advisor-meta">
            <span v-if="advisorRunAt" class="advisor-time">as of {{ fmtTime(advisorRunAt) }}</span>
            <button @click="fetchAdvisor" class="refresh-btn" :disabled="advisorLoading">
              {{ advisorLoading ? 'Loading…' : 'Refresh' }}
            </button>
          </div>
        </div>

        <div v-if="advisorLoading" class="advisor-loading">Analyzing holdings…</div>
        <div v-else-if="advisorError" class="advisor-error">{{ advisorError }}</div>

        <div v-else-if="advisorResults.length" class="advisor-rows">
          <!-- SELL rows -->
          <template v-for="r in advisorResults" :key="r.ticker">
            <div v-if="r.action === 'SELL'" class="advisor-row row-sell">
              <div class="row-left">
                <span class="action-chip chip-sell">SELL</span>
                <span class="row-ticker">{{ r.ticker }}</span>
                <span class="row-account">{{ r.account_name }}</span>
              </div>
              <div class="row-right">
                <span class="row-pnl" :class="r.fx_adjusted_pnl_pct >= 0 ? 'pos' : 'neg'">
                  {{ r.fx_adjusted_pnl_pct > 0 ? '+' : '' }}{{ r.fx_adjusted_pnl_pct.toFixed(1) }}%
                  <span v-if="r.has_fx_cost" class="fx-note">FX-adj</span>
                </span>
                <span v-if="r.earnings_days_away != null && r.earnings_days_away <= 5" class="earn-warn">⚡ Earn {{ r.earnings_days_away }}d</span>
              </div>
              <div class="row-reason">{{ r.reason }}</div>
            </div>
          </template>

          <!-- WATCH rows -->
          <template v-for="r in advisorResults" :key="r.ticker + '-w'">
            <div v-if="r.action === 'WATCH'" class="advisor-row row-watch">
              <div class="row-left">
                <span class="action-chip chip-watch">WATCH</span>
                <span class="row-ticker">{{ r.ticker }}</span>
                <span class="row-account">{{ r.account_name }}</span>
              </div>
              <div class="row-right">
                <span class="row-pnl" :class="r.fx_adjusted_pnl_pct >= 0 ? 'pos' : 'neg'">
                  {{ r.fx_adjusted_pnl_pct > 0 ? '+' : '' }}{{ r.fx_adjusted_pnl_pct.toFixed(1) }}%
                  <span v-if="r.has_fx_cost" class="fx-note">FX-adj</span>
                </span>
              </div>
              <div class="row-reason">{{ r.reason }}</div>
            </div>
          </template>

          <!-- HOLD rows — collapsed by default -->
          <div class="hold-section">
            <button class="hold-toggle" @click="holdExpanded = !holdExpanded">
              {{ holdExpanded ? '▾' : '▸' }} HOLD ({{ advisorHoldCount }})
            </button>
            <template v-if="holdExpanded">
              <div v-for="r in advisorResults.filter(r => r.action === 'HOLD')" :key="r.ticker + '-h'" class="advisor-row row-hold">
                <div class="row-left">
                  <span class="action-chip chip-hold">HOLD</span>
                  <span class="row-ticker">{{ r.ticker }}</span>
                  <span class="row-account">{{ r.account_name }}</span>
                </div>
                <div class="row-right">
                  <span class="row-pnl" :class="r.fx_adjusted_pnl_pct >= 0 ? 'pos' : 'neg'">
                    {{ r.fx_adjusted_pnl_pct > 0 ? '+' : '' }}{{ r.fx_adjusted_pnl_pct.toFixed(1) }}%
                  </span>
                </div>
                <div class="row-reason">{{ r.reason }}</div>
              </div>
            </template>
          </div>

          <!-- Leveraged ETF rows -->
          <template v-for="r in advisorResults" :key="r.ticker + '-l'">
            <div v-if="r.action === 'LEVERAGED_ETF'" class="advisor-row row-leveraged">
              <div class="row-left">
                <span class="action-chip chip-leveraged">⚠️ ETF</span>
                <span class="row-ticker">{{ r.ticker }}</span>
                <span class="row-account">{{ r.account_name }}</span>
              </div>
              <div class="row-right">
                <span class="row-pnl" :class="r.unrealized_pnl_pct >= 0 ? 'pos' : 'neg'">
                  {{ r.unrealized_pnl_pct > 0 ? '+' : '' }}{{ r.unrealized_pnl_pct.toFixed(1) }}%
                </span>
              </div>
              <div class="row-reason">{{ r.reason }}</div>
            </div>
          </template>
        </div>

        <div v-else-if="!advisorLoading" class="advisor-empty">No holdings to analyze.</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { usePortfolioStore } from '../stores/portfolio'
import api from '../services/api'
import HoldingCard from '../components/HoldingCard.vue'

const store = usePortfolioStore()

const advisorResults = ref([])
const advisorRunAt = ref(null)
const advisorLoading = ref(false)
const advisorError = ref(null)
const holdExpanded = ref(false)

const advisorSellCount = computed(() => advisorResults.value.filter(r => r.action === 'SELL').length)
const advisorWatchCount = computed(() => advisorResults.value.filter(r => r.action === 'WATCH').length)
const advisorHoldCount = computed(() => advisorResults.value.filter(r => r.action === 'HOLD').length)

onMounted(() => {
  if (!store.summary) store.fetchSummary()
  fetchAdvisor()
})

async function fetchAdvisor() {
  advisorLoading.value = true
  advisorError.value = null
  try {
    const res = await api.get('/advisor/results')
    advisorResults.value = res.data.results
    advisorRunAt.value = res.data.run_at
  } catch (e) {
    advisorError.value = 'Could not load advisor results.'
  } finally {
    advisorLoading.value = false
  }
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatFlag(flag) {
  if (flag.startsWith('SECTOR_OVERWEIGHT:')) {
    const parts = flag.split(':')
    return `Sector overweight — ${parts[1]} at ${parts[2]}`
  }
  if (flag.startsWith('POSITION_OVERWEIGHT:')) {
    const parts = flag.split(':')
    return `Position overweight — ${parts[1]} at ${parts[2]}`
  }
  return flag.replace(/_/g, ' ')
}
</script>

<style scoped>
.portfolio-page { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }

.loading-state { text-align: center; padding: 60px; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: 22px; font-weight: 700; }
.page-sub { color: var(--text-muted); font-size: 13px; margin-top: 2px; }
.refresh-btn {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.flags-row { display: flex; flex-wrap: wrap; gap: 8px; }

.account-section { display: flex; flex-direction: column; gap: 12px; }
.account-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.account-name { font-size: 16px; font-weight: 700; }
.account-meta { font-size: 12px; color: var(--text-muted); }
.account-pnl { font-size: 16px; font-weight: 700; text-align: right; }
.account-pnl .pct { font-size: 13px; font-weight: 400; margin-left: 4px; }

.holdings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 10px;
}

/* ── Advisor Panel ─────────────────────────────────────────────────────────── */
.advisor-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.advisor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.advisor-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.advisor-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.advisor-time { font-size: 12px; color: var(--text-muted); }

.advisor-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
}
.advisor-badge.sell { background: rgba(239,68,68,0.15); color: #ef4444; }
.advisor-badge.watch { background: rgba(234,179,8,0.15); color: #eab308; }

.advisor-loading, .advisor-error, .advisor-empty {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  padding: 16px 0;
}
.advisor-error { color: #ef4444; }

.advisor-rows { display: flex; flex-direction: column; gap: 6px; }

.advisor-row {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 2px 12px;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid transparent;
}
.row-sell   { background: rgba(239,68,68,0.07);  border-left-color: #ef4444; }
.row-watch  { background: rgba(234,179,8,0.07);  border-left-color: #eab308; }
.row-hold   { background: rgba(34,197,94,0.05);  border-left-color: #22c55e; }
.row-leveraged { background: rgba(107,114,128,0.07); border-left-color: #6b7280; }

.row-left {
  display: flex;
  align-items: center;
  gap: 8px;
  grid-column: 1;
  grid-row: 1;
}
.row-right {
  display: flex;
  align-items: center;
  gap: 6px;
  grid-column: 2;
  grid-row: 1;
  justify-content: flex-end;
}
.row-reason {
  font-size: 12px;
  color: var(--text-muted);
  grid-column: 1 / -1;
  grid-row: 2;
}

.action-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}
.chip-sell      { background: rgba(239,68,68,0.2);  color: #ef4444; }
.chip-watch     { background: rgba(234,179,8,0.2);  color: #eab308; }
.chip-hold      { background: rgba(34,197,94,0.2);  color: #22c55e; }
.chip-leveraged { background: rgba(107,114,128,0.2); color: #9ca3af; }

.row-ticker { font-size: 14px; font-weight: 700; }
.row-account { font-size: 11px; color: var(--text-muted); }

.row-pnl { font-size: 13px; font-weight: 600; }
.row-pnl.pos { color: #22c55e; }
.row-pnl.neg { color: #ef4444; }

.fx-note { font-size: 10px; color: var(--text-muted); margin-left: 3px; font-weight: 400; }
.earn-warn { font-size: 11px; color: #f97316; font-weight: 600; }

.hold-section { display: flex; flex-direction: column; gap: 6px; }
.hold-toggle {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  padding: 4px 0;
}
.hold-toggle:hover { color: var(--text); }
</style>
