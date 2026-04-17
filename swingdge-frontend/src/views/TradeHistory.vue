<template>
  <div class="history">
    <div class="page-header">
      <h1 class="page-title">Trade History</h1>
      <p class="page-sub">Closed, stopped, expired and cancelled trade plans.</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-card card">
      <p class="negative">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <template v-else-if="trades.length === 0">
      <div class="empty-state card">
        <p>No closed trades yet.</p>
        <p class="sub">Trades appear here once they are closed, stopped, expired or cancelled.</p>
      </div>
    </template>

    <template v-else>
      <!-- Summary strip -->
      <div class="summary-strip card">
        <div class="stat">
          <div class="stat-val">{{ stats.total }}</div>
          <div class="stat-label">Total</div>
        </div>
        <div class="stat">
          <div class="stat-val positive">{{ stats.wins }}</div>
          <div class="stat-label">Wins</div>
        </div>
        <div class="stat">
          <div class="stat-val negative">{{ stats.losses }}</div>
          <div class="stat-label">Losses</div>
        </div>
        <div class="stat">
          <div class="stat-val" :class="stats.winRate >= 50 ? 'positive' : 'negative'">
            {{ stats.winRate }}%
          </div>
          <div class="stat-label">Win Rate</div>
        </div>
        <div class="stat">
          <div class="stat-val" :class="stats.totalPnl >= 0 ? 'positive' : 'negative'">
            {{ stats.totalPnl >= 0 ? '+' : '' }}${{ stats.totalPnl.toFixed(2) }}
          </div>
          <div class="stat-label">Total P&amp;L</div>
        </div>
        <div class="stat" v-if="stats.wins > 0">
          <div class="stat-val positive">+${{ stats.avgWin.toFixed(0) }}</div>
          <div class="stat-label">Avg Win</div>
        </div>
        <div class="stat" v-if="stats.losses > 0">
          <div class="stat-val negative">-${{ stats.avgLoss.toFixed(0) }}</div>
          <div class="stat-label">Avg Loss</div>
        </div>
        <div class="stat" v-if="stats.wins > 0 && stats.losses > 0">
          <div class="stat-val" :class="stats.expectancy >= 0 ? 'positive' : 'negative'" :title="'Expected profit per trade = (win rate × avg win) − (loss rate × avg loss). Positive means your system is profitable over time.'">
            {{ stats.expectancy >= 0 ? '+' : '' }}${{ stats.expectancy.toFixed(0) }}
          </div>
          <div class="stat-label">Expectancy</div>
        </div>
      </div>

      <!-- Interpretation -->
      <div v-if="stats.total >= 3" class="interpretation card">
        <p class="interp-line" v-if="stats.expectancy > 0">
          Your system has positive expectancy — on average, each trade earns you ${{ stats.expectancy.toFixed(2) }}. Keep following the rules.
        </p>
        <p class="interp-line" v-else-if="stats.expectancy < 0">
          Your system has negative expectancy right now. Your losses (${{ stats.avgLoss.toFixed(0) }} avg) are outpacing your wins (${{ stats.avgWin.toFixed(0) }} avg). Review your stop placement.
        </p>
        <p class="interp-line" v-if="stats.winRate < 40 && stats.wins > 0">
          Win rate of {{ stats.winRate }}% is low, but with a 2:1 reward/risk target you only need 34%+ to be profitable — focus on letting winners run to T2.
        </p>
        <p class="interp-line" v-if="stats.winRate >= 60">
          Strong {{ stats.winRate }}% win rate. Make sure you're also hitting T2 targets and not exiting early.
        </p>
      </div>

      <!-- Equity curve -->
      <div v-if="equityCurve.length > 1" class="card equity-card">
        <div class="equity-header">
          <span class="equity-title">Equity Curve</span>
          <span class="equity-total" :class="equityFinal >= 0 ? 'positive' : 'negative'">
            {{ equityFinal >= 0 ? '+' : '' }}${{ equityFinal.toFixed(2) }} realized
          </span>
        </div>
        <svg class="equity-svg" :viewBox="`0 0 ${svgW} ${svgH}`" preserveAspectRatio="none">
          <!-- Zero baseline -->
          <line
            :x1="0" :y1="svgZeroY" :x2="svgW" :y2="svgZeroY"
            stroke="var(--border)" stroke-width="1" stroke-dasharray="4 3"
          />
          <!-- Fill area under curve -->
          <path :d="svgFillPath" :fill="equityFinal >= 0 ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)'" />
          <!-- Curve line -->
          <polyline
            :points="svgPoints"
            fill="none"
            :stroke="equityFinal >= 0 ? 'var(--green)' : 'var(--red)'"
            stroke-width="2"
            stroke-linejoin="round"
          />
        </svg>
      </div>

      <!-- Filter chips -->
      <div class="filter-row">
        <button
          v-for="f in filters"
          :key="f.value"
          class="chip"
          :class="{ active: activeFilter === f.value }"
          @click="activeFilter = f.value"
        >
          {{ f.label }}
          <span class="chip-count">{{ f.count }}</span>
        </button>
      </div>

      <!-- Trade rows -->
      <div class="trade-list card">
        <div
          v-for="t in filtered"
          :key="t.id"
          class="trade-row"
          @click="$router.push(`/trades/${t.id}`)"
        >
          <!-- Left: ticker + meta -->
          <div class="trade-left">
            <div class="trade-top">
              <span class="ticker">{{ t.ticker }}</span>
              <span class="badge exchange">{{ t.exchange }}</span>
              <span v-if="t.sector" class="badge sector">{{ t.sector }}</span>
              <span v-if="t.signal_type" class="badge signal" :class="signalClass(t.signal_type)">
                {{ formatSignal(t.signal_type) }}
              </span>
            </div>
            <div class="trade-dates">
              <span>Opened {{ formatDate(t.created_at) }}</span>
              <span v-if="t.closed_at"> · Closed {{ formatDate(t.closed_at) }}</span>
            </div>
          </div>

          <!-- Middle: price journey -->
          <div class="trade-prices">
            <div class="price-col">
              <div class="price-label">Entry mid</div>
              <div class="price-val">${{ entryMid(t).toFixed(2) }}</div>
            </div>
            <div class="price-arrow">→</div>
            <div class="price-col">
              <div class="price-label">{{ t.closed_price ? 'Exit' : 'T2 target' }}</div>
              <div class="price-val">
                ${{ (t.closed_price ?? t.target_2).toFixed(2) }}
              </div>
            </div>
          </div>

          <!-- Right: P&L + status -->
          <div class="trade-right">
            <div
              v-if="t.actual_pnl != null"
              class="pnl"
              :class="t.actual_pnl >= 0 ? 'positive' : 'negative'"
            >
              {{ t.actual_pnl >= 0 ? '+' : '' }}${{ t.actual_pnl.toFixed(2) }}
            </div>
            <div v-else class="pnl muted">—</div>
            <span class="status-badge" :class="statusClass(t.status)">
              {{ formatStatus(t.status) }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { tradesApi } from '../services/api'

const trades = ref([])
const loading = ref(false)
const error = ref(null)
const activeFilter = ref('all')

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await tradesApi.getHistory()
    trades.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load history'
  } finally {
    loading.value = false
  }
}

// ── Stats ─────────────────────────────────────────────────────────────────────

const stats = computed(() => {
  const closed = trades.value.filter((t) => t.actual_pnl != null)
  const winTrades = closed.filter((t) => t.actual_pnl > 0)
  const lossTrades = closed.filter((t) => t.actual_pnl <= 0)
  const wins = winTrades.length
  const losses = lossTrades.length
  const totalPnl = closed.reduce((sum, t) => sum + t.actual_pnl, 0)
  const winRate = closed.length > 0 ? Math.round((wins / closed.length) * 100) : 0
  const avgWin = wins > 0 ? winTrades.reduce((s, t) => s + t.actual_pnl, 0) / wins : 0
  const avgLoss = losses > 0 ? Math.abs(lossTrades.reduce((s, t) => s + t.actual_pnl, 0) / losses) : 0
  const wr = closed.length > 0 ? wins / closed.length : 0
  const expectancy = (wr * avgWin) - ((1 - wr) * avgLoss)
  return { total: trades.value.length, wins, losses, winRate, totalPnl, avgWin, avgLoss, expectancy }
})

// ── Equity curve ─────────────────────────────────────────────────────────────

const svgW = 600
const svgH = 80
const svgPad = 8

const equityCurve = computed(() => {
  const closed = [...trades.value]
    .filter((t) => t.actual_pnl != null && t.closed_at)
    .sort((a, b) => new Date(a.closed_at) - new Date(b.closed_at))
  let cumulative = 0
  return closed.map((t) => { cumulative += t.actual_pnl; return cumulative })
})

const equityFinal = computed(() => equityCurve.value.at(-1) ?? 0)

const svgZeroY = computed(() => {
  const curve = equityCurve.value
  if (!curve.length) return svgH / 2
  const min = Math.min(0, ...curve)
  const max = Math.max(0, ...curve)
  const range = max - min || 1
  return svgPad + ((max - 0) / range) * (svgH - svgPad * 2)
})

const svgPoints = computed(() => {
  const curve = equityCurve.value
  if (curve.length < 2) return ''
  const min = Math.min(0, ...curve)
  const max = Math.max(0, ...curve)
  const range = max - min || 1
  return curve.map((v, i) => {
    const x = svgPad + (i / (curve.length - 1)) * (svgW - svgPad * 2)
    const y = svgPad + ((max - v) / range) * (svgH - svgPad * 2)
    return `${x},${y}`
  }).join(' ')
})

const svgFillPath = computed(() => {
  const curve = equityCurve.value
  if (curve.length < 2) return ''
  const min = Math.min(0, ...curve)
  const max = Math.max(0, ...curve)
  const range = max - min || 1
  const zeroY = svgZeroY.value
  const pts = curve.map((v, i) => {
    const x = svgPad + (i / (curve.length - 1)) * (svgW - svgPad * 2)
    const y = svgPad + ((max - v) / range) * (svgH - svgPad * 2)
    return [x, y]
  })
  const firstX = pts[0][0]
  const lastX = pts[pts.length - 1][0]
  const linePts = pts.map(([x, y]) => `${x},${y}`).join(' L')
  return `M${firstX},${zeroY} L${linePts} L${lastX},${zeroY} Z`
})

// ── Filters ───────────────────────────────────────────────────────────────────

const filters = computed(() => [
  { label: 'All',       value: 'all',       count: trades.value.length },
  { label: 'Won',       value: 'hit_t2',    count: trades.value.filter((t) => t.status === 'hit_t2').length },
  { label: 'Stopped',   value: 'stopped',   count: trades.value.filter((t) => t.status === 'stopped').length },
  { label: 'Expired',   value: 'expired',   count: trades.value.filter((t) => t.status === 'expired').length },
  { label: 'Cancelled', value: 'cancelled', count: trades.value.filter((t) => t.status === 'cancelled').length },
].filter((f) => f.value === 'all' || f.count > 0))

const filtered = computed(() =>
  activeFilter.value === 'all'
    ? trades.value
    : trades.value.filter((t) => t.status === activeFilter.value)
)

// ── Helpers ───────────────────────────────────────────────────────────────────

function entryMid(t) {
  return (t.entry_low + t.entry_high) / 2
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSignal(s) {
  const map = {
    RSI_PULLBACK: 'RSI Pullback',
    RSI_REVERSAL: 'RSI Reversal',
    MACD_CROSSOVER: 'MACD Cross',
    EMA_CROSSOVER: 'EMA Cross',
    BB_BOUNCE: 'BB Bounce',
    VOLUME_BREAKOUT: 'Vol Break',
    COMBO: 'COMBO',
  }
  return map[s] || s
}

function formatStatus(s) {
  const map = {
    hit_t2: 'Hit T2',
    hit_t1: 'Hit T1',
    stopped: 'Stopped',
    expired: 'Expired',
    cancelled: 'Cancelled',
  }
  return map[s] || s
}

function statusClass(s) {
  if (s === 'hit_t2' || s === 'hit_t1') return 'win'
  if (s === 'stopped') return 'loss'
  if (s === 'expired' || s === 'cancelled') return 'neutral'
  return ''
}

function signalClass(s) {
  const map = {
    RSI_PULLBACK: 'sig-rsi-pull',
    RSI_REVERSAL: 'sig-rsi-rev',
    MACD_CROSSOVER: 'sig-macd',
    EMA_CROSSOVER: 'sig-ema',
    BB_BOUNCE: 'sig-bb',
    VOLUME_BREAKOUT: 'sig-vol',
    COMBO: 'sig-combo',
  }
  return map[s] || ''
}

onMounted(load)
</script>

<style scoped>
.history { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

.page-header {}
.page-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.page-sub { font-size: 13px; color: var(--text-muted); }

/* Loading / error / empty */
.loading-state { text-align: center; padding: 40px 16px; }
.error-card, .empty-state { text-align: center; padding: 32px 16px; }
.empty-state .sub { font-size: 13px; color: var(--text-muted); margin-top: 6px; }
.retry-btn { margin-top: 12px; background: var(--border); color: var(--text); border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; }

/* Interpretation */
.interpretation {
  background: color-mix(in srgb, var(--accent) 6%, var(--bg-card));
  border-color: color-mix(in srgb, var(--accent) 20%, transparent);
}
.interp-line { font-size: 13px; color: var(--text); line-height: 1.6; margin: 0; }
.interp-line + .interp-line { margin-top: 6px; }

/* Summary strip */
.summary-strip {
  display: flex;
  gap: 0;
  padding: 0;
  overflow: hidden;
  flex-wrap: wrap;
}
.stat {
  flex: 1;
  text-align: center;
  padding: 14px 8px;
  border-right: 1px solid var(--border);
}
.stat:last-child { border-right: none; }
.stat-val { font-size: 20px; font-weight: 700; }
.stat-label { font-size: 11px; color: var(--text-muted); margin-top: 2px; text-transform: uppercase; letter-spacing: 0.05em; }

/* Filter chips */
.filter-row { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  display: flex; align-items: center; gap: 6px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); padding: 5px 12px; border-radius: 20px;
  font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.15s;
}
.chip.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.chip-count { font-size: 11px; opacity: 0.7; }

/* Trade list */
.trade-list { display: flex; flex-direction: column; gap: 0; padding: 0; overflow: hidden; }

.trade-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.1s;
}
.trade-row:last-child { border-bottom: none; }
.trade-row:hover { background: var(--surface); }

/* Left */
.trade-left { flex: 1; min-width: 0; }
.trade-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.ticker { font-size: 15px; font-weight: 700; }
.trade-dates { font-size: 11px; color: var(--text-muted); }

/* Middle */
.trade-prices { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.price-col { text-align: center; }
.price-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.price-val { font-size: 13px; font-weight: 600; margin-top: 2px; }
.price-arrow { color: var(--text-muted); font-size: 12px; }

/* Right */
.trade-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0; }
.pnl { font-size: 16px; font-weight: 700; }
.pnl.muted { color: var(--text-muted); }

/* Badges */
.badge {
  font-size: 10px; font-weight: 600; padding: 2px 6px;
  border-radius: 4px; text-transform: uppercase; letter-spacing: 0.04em;
}
.badge.exchange { background: color-mix(in srgb, var(--text-muted) 15%, transparent); color: var(--text-muted); }
.badge.sector   { background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); }

.status-badge {
  font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;
}
.status-badge.win     { background: color-mix(in srgb, var(--green) 20%, transparent); color: var(--green); }
.status-badge.loss    { background: color-mix(in srgb, var(--red) 20%, transparent); color: var(--red); }
.status-badge.neutral { background: color-mix(in srgb, var(--text-muted) 15%, transparent); color: var(--text-muted); }

/* Signal colors */
.badge.signal { }
.sig-rsi-pull  { background: color-mix(in srgb, #3b82f6 20%, transparent); color: #3b82f6; }
.sig-rsi-rev   { background: color-mix(in srgb, #8b5cf6 20%, transparent); color: #8b5cf6; }
.sig-macd      { background: color-mix(in srgb, #06b6d4 20%, transparent); color: #06b6d4; }
.sig-ema       { background: color-mix(in srgb, #f59e0b 20%, transparent); color: #f59e0b; }
.sig-bb        { background: color-mix(in srgb, #ec4899 20%, transparent); color: #ec4899; }
.sig-vol       { background: color-mix(in srgb, #10b981 20%, transparent); color: #10b981; }
.sig-combo     { background: color-mix(in srgb, #f97316 20%, transparent); color: #f97316; }

/* Equity curve */
.equity-card { padding: 14px 16px; }
.equity-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.equity-title { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.equity-total { font-size: 13px; font-weight: 700; }
.equity-svg { width: 100%; height: 80px; display: block; }

/* Shared */
.positive { color: var(--green); }
.negative { color: var(--red); }

@media (max-width: 640px) {
  .trade-prices { display: none; }
  .trade-row { gap: 10px; }
}
</style>
