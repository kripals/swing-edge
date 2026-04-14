<template>
  <div class="scanner">
    <!-- Header -->
    <div class="header-row">
      <div>
        <h1 class="page-title">Scanner</h1>
        <p v-if="lastMeta" class="scan-meta">
          {{ lastMeta.candidates_found }} candidates &middot;
          {{ formatDate(lastMeta.scan_date) }} &middot;
          {{ lastMeta.duration_ms }}ms
        </p>
      </div>
      <button
        class="run-btn"
        :class="{ scanning }"
        :disabled="scanning"
        @click="runScan"
      >
        {{ scanning ? 'Scanning…' : 'Run Scan' }}
      </button>
    </div>

    <!-- Scanning state -->
    <div v-if="scanning" class="loading-state">
      <div class="spinner"></div>
      <p class="loading-msg">Scanning {{ tickerCount }}+ tickers{{ dots }}</p>
      <p class="loading-sub">This takes 15–30 seconds on the free API tier</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-card card">
      <p class="negative">{{ error }}</p>
      <button class="retry-btn" @click="loadResults()">Retry</button>
    </div>

    <template v-else>
      <!-- Controls row: date picker + signal filter -->
      <div class="controls-row">
        <div class="date-group">
          <label class="label">Date</label>
          <input
            type="date"
            v-model="selectedDate"
            class="date-input"
            @change="loadResults(selectedDate)"
          />
        </div>

        <div class="filter-chips">
          <button
            v-for="sig in signalTypes"
            :key="sig"
            class="chip"
            :class="{ active: signalFilter === sig }"
            @click="signalFilter = signalFilter === sig ? null : sig"
          >
            {{ formatSignal(sig) }}
          </button>
        </div>
      </div>

      <!-- No results state -->
      <div v-if="filtered.length === 0 && !loading" class="empty-card card">
        <p class="empty-title">No candidates</p>
        <p class="empty-sub">
          {{ candidates.length === 0
            ? 'Run a scan to find swing trade candidates.'
            : 'No candidates match the selected filter.' }}
        </p>
      </div>

      <!-- Loading results -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
      </div>

      <!-- Candidates list -->
      <!-- Legend -->
      <div v-if="!loading && filtered.length" class="legend-row">
        <span class="legend-label">Signal strength:</span>
        <span class="legend-item strong-bar-ex">Strong (70%+)</span>
        <span class="legend-item medium-bar-ex">Medium (50–70%)</span>
        <span class="legend-item weak-bar-ex">Weak (40–50%)</span>
        <InfoTooltip text="A score out of 9 criteria: uptrend, RSI zone, MACD direction, EMA crossover, Bollinger Band, volume, relative strength vs TSX. 40% minimum to appear here." position="bottom" />
      </div>

      <div v-if="!loading && filtered.length" class="candidates">
        <div
          v-for="c in filtered"
          :key="c.ticker"
          class="candidate-card card"
        >
          <!-- Top row: ticker + signal badge + action -->
          <div class="candidate-top">
            <div class="ticker-block">
              <span class="ticker">{{ c.ticker }}</span>
              <span class="exchange-badge">{{ c.exchange }}</span>
              <span v-if="c.sector" class="sector-badge">{{ c.sector }}</span>
            </div>
            <div class="signal-block">
              <span class="signal-badge" :class="signalClass(c.signal_type)">
                {{ formatSignal(c.signal_type) }}
              </span>
              <div class="strength-bar-wrap" title="Signal strength">
                <div
                  class="strength-bar"
                  :style="{ width: (c.signal_strength * 100) + '%' }"
                  :class="strengthClass(c.signal_strength)"
                ></div>
              </div>
              <span class="strength-label">{{ pct(c.signal_strength) }}</span>
            </div>
            <button class="plan-btn" @click="goToPlan(c.ticker, c.signal_type)">
              Plan →
            </button>
          </div>

          <!-- Indicator chips -->
          <div class="indicator-row">
            <span class="ind-chip" v-if="c.current_price != null">
              ${{ fmt(c.current_price) }}
            </span>
            <span class="ind-chip" :class="rsiClass(c.rsi_14)" v-if="c.rsi_14 != null"
              :title="`RSI (Relative Strength Index): measures momentum 0–100. Under 30 = oversold/potential buy. Over 70 = overbought. Current: ${fmt(c.rsi_14)}`">
              RSI {{ fmt(c.rsi_14) }}
            </span>
            <span class="ind-chip" v-if="c.volume_ratio != null"
              :title="`Volume ratio: today's trading volume vs 20-day average. ${fmt(c.volume_ratio)}× means ${fmt(c.volume_ratio)} times the normal volume. Higher = more interest.`">
              Vol {{ fmt(c.volume_ratio) }}x
            </span>
            <span class="ind-chip" :class="c.above_sma_50 ? 'chip-green' : 'chip-red'"
              :title="c.above_sma_50 ? 'Price is above the 50-day moving average — stock is in an uptrend.' : 'Price is below the 50-day moving average — stock is in a downtrend. Most buy signals require being above this line.'">
              {{ c.above_sma_50 ? '▲ SMA50' : '▼ SMA50' }}
            </span>
            <span class="ind-chip" v-if="c.relative_strength != null" :class="c.relative_strength > 0 ? 'chip-green' : 'chip-red'"
              :title="`Relative Strength vs TSX Composite over 20 days. Positive means this stock is outperforming the overall market.`">
              RS {{ c.relative_strength > 0 ? '+' : '' }}{{ fmt(c.relative_strength) }}%
            </span>
            <span class="ind-chip warning-chip" v-if="c.earnings_days_away != null && c.earnings_days_away <= 10"
              :title="`Earnings report in ${c.earnings_days_away} days. Stocks can move 5–20% on earnings — we avoid new trades within 5 days of earnings.`">
              Earnings {{ c.earnings_days_away }}d
            </span>
          </div>

          <!-- Signals list (active conditions) -->
          <div v-if="c.signals && c.signals.length" class="signals-list">
            <span v-for="s in c.signals" :key="s" class="signal-tag" :title="signalExplain(s)">{{ formatSignal(s) }}</span>
          </div>

          <!-- Notes -->
          <p v-if="c.notes" class="candidate-notes">{{ c.notes }}</p>
        </div>
      </div>

      <!-- History footer -->
      <div v-if="history.length" class="history-row">
        <span class="label">Past scans:</span>
        <button
          v-for="h in history.slice(0, 7)"
          :key="h.scan_date"
          class="history-chip"
          :class="{ active: selectedDate === h.scan_date }"
          @click="selectHistory(h.scan_date)"
        >
          {{ shortDate(h.scan_date) }} ({{ h.count }})
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { scannerApi } from '../services/api'
import InfoTooltip from '../components/InfoTooltip.vue'

const router = useRouter()

const candidates = ref([])
const history = ref([])
const lastMeta = ref(null)
const loading = ref(false)
const scanning = ref(false)
const error = ref(null)
const signalFilter = ref(null)
const selectedDate = ref(todayStr())
const dots = ref('')
const tickerCount = 56

let dotInterval

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

const signalTypes = computed(() => {
  const types = new Set(candidates.value.map(c => c.signal_type))
  return [...types].sort()
})

const filtered = computed(() => {
  if (!signalFilter.value) return candidates.value
  return candidates.value.filter(c => c.signal_type === signalFilter.value)
})

async function loadResults(date) {
  loading.value = true
  error.value = null
  try {
    const [resultsRes, historyRes] = await Promise.all([
      scannerApi.getResults(date),
      scannerApi.getHistory(),
    ])
    candidates.value = resultsRes.data
    history.value = historyRes.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load scan results'
  } finally {
    loading.value = false
  }
}

async function runScan() {
  scanning.value = true
  error.value = null
  candidates.value = []
  lastMeta.value = null
  dotInterval = setInterval(() => {
    dots.value = dots.value.length >= 3 ? '' : dots.value + '.'
  }, 500)

  try {
    const res = await scannerApi.runScan()
    const data = res.data
    candidates.value = data.candidates
    lastMeta.value = {
      candidates_found: data.candidates_found,
      scan_date: data.scan_date,
      duration_ms: data.duration_ms,
    }
    selectedDate.value = data.scan_date
    // refresh history after a run
    const histRes = await scannerApi.getHistory()
    history.value = histRes.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Scan failed — check backend logs'
  } finally {
    scanning.value = false
    clearInterval(dotInterval)
    dots.value = ''
  }
}

function selectHistory(date) {
  selectedDate.value = date
  loadResults(date)
}

function goToPlan(ticker, signalType) {
  router.push({ path: '/plan', query: { ticker, signal_type: signalType } })
}

// ── Formatters ────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toFixed(2)
}

function pct(n) {
  if (n == null) return '—'
  return (Number(n) * 100).toFixed(0) + '%'
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' })
}

function shortDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })
}

function formatSignal(type) {
  const map = {
    RSI_PULLBACK: 'RSI Pullback',
    RSI_REVERSAL: 'RSI Reversal',
    MACD_CROSSOVER: 'MACD Cross',
    EMA_CROSSOVER: 'EMA Cross',
    BB_BOUNCE: 'BB Bounce',
    VOLUME_BREAKOUT: 'Vol Breakout',
    COMBO: 'Combo',
  }
  return map[type] || type
}

function signalExplain(type) {
  const map = {
    RSI_PULLBACK: 'RSI between 30–50 while above SMA 50 — stock pulled back in an uptrend, potential re-entry.',
    RSI_REVERSAL: 'RSI crossed above 30 from oversold territory — potential bottom bounce.',
    MACD_CROSSOVER: 'MACD histogram turned positive — momentum has shifted from bearish to bullish.',
    EMA_CROSSOVER: '9-day EMA crossed above 21-day EMA — short-term trend turned bullish.',
    BB_BOUNCE: 'Price is near or below the lower Bollinger Band — statistically oversold, mean reversion likely.',
    VOLUME_BREAKOUT: 'Price above SMA 50 and 200 on more than 2× normal volume — institutional buying pressure.',
    COMBO: 'Two or more signals fired at once — higher conviction setup.',
  }
  return map[type] || type
}

function signalClass(type) {
  const map = {
    RSI_PULLBACK: 'sig-blue',
    RSI_REVERSAL: 'sig-green',
    MACD_CROSSOVER: 'sig-purple',
    EMA_CROSSOVER: 'sig-teal',
    BB_BOUNCE: 'sig-yellow',
    VOLUME_BREAKOUT: 'sig-orange',
    COMBO: 'sig-accent',
  }
  return map[type] || 'sig-blue'
}

function strengthClass(s) {
  if (s >= 0.7) return 'strong-bar'
  if (s >= 0.5) return 'medium-bar'
  return 'weak-bar'
}

function rsiClass(rsi) {
  if (rsi == null) return ''
  if (rsi <= 35) return 'chip-green'
  if (rsi >= 70) return 'chip-red'
  return ''
}

onMounted(() => loadResults())
</script>

<style scoped>
.scanner { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

/* Header */
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: 22px; font-weight: 700; }
.scan-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.run-btn {
  background: var(--accent);
  color: #fff;
  border: none;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.run-btn:disabled { opacity: 0.6; cursor: default; }
.run-btn.scanning { background: var(--border); color: var(--text-muted); }

/* Loading */
.loading-state { text-align: center; padding: 40px 16px; }
.loading-msg { color: var(--text-muted); margin-top: 12px; }
.loading-sub { color: var(--text-muted); font-size: 12px; margin-top: 6px; }

/* Error */
.error-card { text-align: center; }
.retry-btn {
  margin-top: 12px;
  background: var(--border);
  color: var(--text);
  border: none;
  padding: 6px 16px;
  border-radius: 6px;
  cursor: pointer;
}

/* Controls */
.controls-row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.date-group { display: flex; align-items: center; gap: 8px; }
.label { font-size: 12px; color: var(--text-muted); }
.date-input {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.filter-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.chip.active, .chip:hover { border-color: var(--accent); color: var(--accent); background: rgba(99,102,241,0.1); }

/* Empty */
.empty-card { text-align: center; padding: 40px 16px; }
.empty-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.empty-sub { color: var(--text-muted); font-size: 13px; }

/* Legend */
.legend-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); }
.legend-label { font-weight: 600; }
.legend-item { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.strong-bar-ex { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
.medium-bar-ex { background: rgba(245,158,11,0.15); color: var(--yellow); border: 1px solid rgba(245,158,11,0.25); }
.weak-bar-ex   { background: rgba(59,130,246,0.15);  color: var(--blue);   border: 1px solid rgba(59,130,246,0.25); }

/* Candidates */
.candidates { display: flex; flex-direction: column; gap: 10px; }

.candidate-card { display: flex; flex-direction: column; gap: 10px; }

.candidate-top {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ticker-block { display: flex; align-items: center; gap: 6px; min-width: 140px; }
.ticker { font-size: 16px; font-weight: 700; }
.exchange-badge {
  font-size: 10px;
  background: var(--border);
  color: var(--text-muted);
  padding: 2px 5px;
  border-radius: 4px;
}
.sector-badge {
  font-size: 10px;
  color: var(--text-muted);
  background: rgba(99,102,241,0.1);
  border: 1px solid rgba(99,102,241,0.25);
  padding: 2px 5px;
  border-radius: 4px;
}

.signal-block { display: flex; align-items: center; gap: 8px; flex: 1; }
.signal-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

/* Signal type colors */
.sig-blue   { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); }
.sig-green  { background: rgba(34,197,94,0.15);  color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.sig-purple { background: rgba(168,85,247,0.15); color: #c084fc; border: 1px solid rgba(168,85,247,0.3); }
.sig-teal   { background: rgba(20,184,166,0.15); color: #2dd4bf; border: 1px solid rgba(20,184,166,0.3); }
.sig-yellow { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
.sig-orange { background: rgba(249,115,22,0.15); color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
.sig-accent { background: rgba(99,102,241,0.15); color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }

.strength-bar-wrap {
  flex: 1;
  max-width: 80px;
  height: 6px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.strength-bar { height: 100%; border-radius: 4px; transition: width 0.4s; }
.strong-bar { background: var(--green); }
.medium-bar { background: var(--yellow); }
.weak-bar   { background: var(--blue); }
.strength-label { font-size: 12px; color: var(--text-muted); min-width: 32px; }

.plan-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: 5px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.plan-btn:hover { background: rgba(99,102,241,0.1); }

/* Indicator chips */
.indicator-row { display: flex; flex-wrap: wrap; gap: 6px; }
.ind-chip {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--border);
  color: var(--text-muted);
}
.chip-green { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
.chip-red   { background: rgba(239,68,68,0.15); color: var(--red);   border: 1px solid rgba(239,68,68,0.25); }
.warning-chip { background: rgba(245,158,11,0.15); color: var(--yellow); border: 1px solid rgba(245,158,11,0.25); }

/* Active signals */
.signals-list { display: flex; flex-wrap: wrap; gap: 5px; }
.signal-tag {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 2px 6px;
  border-radius: 4px;
}

/* Notes */
.candidate-notes {
  font-size: 12px;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  padding-top: 8px;
}

/* History footer */
.history-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 4px;
}
.history-chip {
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.history-chip:hover, .history-chip.active {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
