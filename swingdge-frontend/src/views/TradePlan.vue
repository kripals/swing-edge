<template>
  <div class="trade-plan">
    <!-- Back -->
    <button class="back-btn" @click="$router.back()">← Back</button>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p class="loading-msg">Generating trade plan…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-card card">
      <p class="negative">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <template v-else-if="plan">
      <!-- Header -->
      <div class="plan-header card">
        <div class="header-left">
          <div class="ticker-row">
            <span class="ticker">{{ plan.ticker }}</span>
            <span class="exchange-badge">{{ plan.exchange }}</span>
            <span class="currency-badge" :class="plan.currency === 'USD' ? 'usd' : 'cad'">
              {{ plan.currency }}
            </span>
            <span v-if="plan.sector" class="sector-badge">{{ plan.sector }}</span>
          </div>
          <div class="plan-meta">
            <span v-if="plan.signal_type" class="signal-badge" :class="signalClass(plan.signal_type)">
              {{ formatSignal(plan.signal_type) }}
            </span>
            <span v-if="plan.signal_score != null" class="score-label">
              Score {{ pct(plan.signal_score) }}
            </span>
            <span v-if="savedPlan" class="status-badge" :class="'status-' + savedPlan.status">
              {{ savedPlan.status.replace('_', ' ') }}
            </span>
          </div>
        </div>
        <div class="header-right">
          <div class="current-price">${{ fmt(plan.current_price) }}</div>
          <div class="price-label">current price</div>
        </div>
      </div>

      <!-- Violations -->
      <div v-if="plan.violations && plan.violations.length" class="violations-card card">
        <div class="violations-title">Rule Violations</div>
        <div v-for="v in plan.violations" :key="v" class="violation-row">
          <span class="violation-icon">!</span>
          {{ v }}
        </div>
      </div>

      <!-- FX Warning -->
      <div v-if="plan.fx_warning" class="warning-card card">
        <span class="warning-icon">⚠</span>
        US stock: {{ plan.fx_cost_pct }}% FX round-trip ({{ plan.currency }} via Wealthsimple).
        Net gain after FX: {{ plan.net_gain_after_fx != null ? plan.net_gain_after_fx.toFixed(1) + '%' : '—' }}
      </div>

      <!-- Earnings Warning -->
      <div v-if="plan.earnings_days_away != null && plan.earnings_days_away <= 10" class="warning-card card earnings-warning">
        <span class="warning-icon">📅</span>
        Earnings in <strong>{{ plan.earnings_days_away }} days</strong>
        <span v-if="plan.earnings_date"> ({{ plan.earnings_date }})</span>
        <span v-if="plan.earnings_days_away <= 5" class="negative"> — inside blackout window</span>
      </div>

      <!-- Price Ladder -->
      <div class="card">
        <h3 class="section-title">Price Levels</h3>
        <div class="price-ladder">
          <PriceLadder
            :stop="plan.stop_loss"
            :entry-low="plan.entry_low"
            :entry-high="plan.entry_high"
            :target1="plan.target_1"
            :target2="plan.target_2"
            :current="plan.current_price"
          />
        </div>

        <!-- Level table -->
        <div class="level-table">
          <div class="level-row t2-row">
            <span class="level-dot green-dot"></span>
            <span class="level-name">Target 2 (full exit)</span>
            <span class="level-price">${{ fmt(plan.target_2) }}</span>
            <span class="level-pct positive">+{{ fromEntry(plan.target_2) }}%</span>
          </div>
          <div class="level-row t1-row">
            <span class="level-dot green-dot faded"></span>
            <span class="level-name">Target 1 (partial exit)</span>
            <span class="level-price">${{ fmt(plan.target_1) }}</span>
            <span class="level-pct positive">+{{ fromEntry(plan.target_1) }}%</span>
          </div>
          <div class="level-row entry-row">
            <span class="level-dot blue-dot"></span>
            <span class="level-name">Entry zone</span>
            <span class="level-price">${{ fmt(plan.entry_low) }} – ${{ fmt(plan.entry_high) }}</span>
            <span class="level-pct muted">mid ${{ fmt(plan.entry_mid || plan.current_price) }}</span>
          </div>
          <div class="level-row stop-row">
            <span class="level-dot red-dot"></span>
            <span class="level-name">Stop loss</span>
            <span class="level-price">${{ fmt(plan.stop_loss) }}</span>
            <span class="level-pct negative">{{ fromEntry(plan.stop_loss) }}%</span>
          </div>
        </div>
      </div>

      <!-- Key Metrics -->
      <div class="metrics-grid">
        <div class="metric-card card">
          <div class="metric-label">Risk/Reward</div>
          <div class="metric-value" :class="rrClass(plan.risk_reward_ratio)">
            {{ plan.risk_reward_ratio }}:1
          </div>
        </div>
        <div class="metric-card card">
          <div class="metric-label">Position Size</div>
          <div class="metric-value">${{ fmtK(plan.position_size_dollars) }}</div>
          <div class="metric-sub">{{ plan.position_size_shares != null ? Math.floor(plan.position_size_shares) + ' shares' : '' }}</div>
        </div>
        <div class="metric-card card">
          <div class="metric-label">Risk Amount</div>
          <div class="metric-value negative">${{ fmt(plan.risk_amount) }}</div>
          <div class="metric-sub">1% of account</div>
        </div>
        <div class="metric-card card">
          <div class="metric-label">FX Cost</div>
          <div class="metric-value" :class="plan.fx_cost_pct > 0 ? 'warning' : 'positive'">
            {{ plan.fx_cost_pct > 0 ? plan.fx_cost_pct + '%' : 'None' }}
          </div>
          <div class="metric-sub">{{ plan.fx_cost_pct > 0 ? 'round-trip' : 'CAD stock' }}</div>
        </div>
      </div>

      <!-- Notes (saved plan only) -->
      <div v-if="savedPlan" class="card">
        <h3 class="section-title">Notes</h3>
        <textarea
          v-model="notes"
          class="notes-input"
          placeholder="Add trade notes…"
          rows="3"
        ></textarea>
        <button
          v-if="notes !== (savedPlan.notes || '')"
          class="save-notes-btn"
          :disabled="savingNotes"
          @click="saveNotes"
        >
          {{ savingNotes ? 'Saving…' : 'Save Notes' }}
        </button>
      </div>

      <!-- Actions: preview mode -->
      <div v-if="!savedPlan" class="action-bar card">
        <p class="action-hint">
          This is a preview — saving will create an active trade plan.
        </p>
        <div class="action-btns">
          <button
            class="action-btn primary"
            :disabled="saving || (plan.violations && plan.violations.length > 0)"
            @click="savePlan"
          >
            {{ saving ? 'Saving…' : 'Save Plan' }}
          </button>
          <span v-if="plan.violations && plan.violations.length > 0" class="violation-hint">
            Fix violations before saving
          </span>
        </div>
      </div>

      <!-- Actions: saved plan status controls -->
      <div v-else class="action-bar card">
        <h3 class="section-title">Update Status</h3>
        <div class="status-btns">
          <button
            v-for="s in availableStatuses"
            :key="s.value"
            class="status-btn"
            :class="['status-btn-' + s.color, { active: savedPlan.status === s.value }]"
            :disabled="updatingStatus"
            @click="updateStatus(s.value)"
          >
            {{ s.label }}
          </button>
        </div>
        <div v-if="needsClosePrice" class="close-price-row">
          <label class="label">Close price</label>
          <input v-model.number="closePrice" type="number" step="0.01" class="close-input" placeholder="0.00" />
          <button class="save-close-btn" @click="confirmClose" :disabled="!closePrice">Confirm</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { tradesApi } from '../services/api'

// Inline price ladder component
import { defineComponent, h } from 'vue'

const PriceLadder = defineComponent({
  props: ['stop', 'entryLow', 'entryHigh', 'target1', 'target2', 'current'],
  setup(props) {
    return () => {
      const levels = [props.stop, props.entryLow, props.entryHigh, props.target1, props.target2]
      const min = Math.min(...levels) * 0.998
      const max = Math.max(...levels) * 1.002
      const range = max - min

      const toY = (price) => 100 - ((price - min) / range) * 100

      const t2y = toY(props.target2)
      const t1y = toY(props.target1)
      const ehY = toY(props.entryHigh)
      const elY = toY(props.entryLow)
      const sy = toY(props.stop)
      const cy = toY(props.current)

      return h('svg', {
        viewBox: '0 0 200 160',
        style: 'width:100%;max-width:280px;display:block;margin:0 auto',
      }, [
        // Stop → Entry fill (red)
        h('rect', { x: 70, y: ehY + '%', width: 60, height: (elY - ehY) + '%', fill: 'rgba(59,130,246,0.15)', rx: 2 }),
        // T1 line
        h('line', { x1: 60, y1: t2y + '%', x2: 140, y2: t2y + '%', stroke: '#22c55e', 'stroke-width': 2 }),
        h('line', { x1: 60, y1: t1y + '%', x2: 140, y2: t1y + '%', stroke: '#22c55e', 'stroke-width': 1.5, 'stroke-dasharray': '4,2' }),
        // Entry zone
        h('line', { x1: 60, y1: ehY + '%', x2: 140, y2: ehY + '%', stroke: '#3b82f6', 'stroke-width': 1 }),
        h('line', { x1: 60, y1: elY + '%', x2: 140, y2: elY + '%', stroke: '#3b82f6', 'stroke-width': 1 }),
        // Stop line
        h('line', { x1: 60, y1: sy + '%', x2: 140, y2: sy + '%', stroke: '#ef4444', 'stroke-width': 2 }),
        // Current price dot
        h('circle', { cx: 100, cy: cy + '%', r: 4, fill: '#f59e0b' }),
        // Labels
        h('text', { x: 145, y: t2y + '%', fill: '#22c55e', 'font-size': 9, 'dominant-baseline': 'middle' }, `T2 $${Number(props.target2).toFixed(2)}`),
        h('text', { x: 145, y: t1y + '%', fill: '#4ade80', 'font-size': 9, 'dominant-baseline': 'middle' }, `T1 $${Number(props.target1).toFixed(2)}`),
        h('text', { x: 145, y: ((ehY + elY) / 2) + '%', fill: '#60a5fa', 'font-size': 9, 'dominant-baseline': 'middle' }, 'Entry'),
        h('text', { x: 145, y: sy + '%', fill: '#ef4444', 'font-size': 9, 'dominant-baseline': 'middle' }, `SL $${Number(props.stop).toFixed(2)}`),
        h('text', { x: 52, y: cy + '%', fill: '#f59e0b', 'font-size': 9, 'dominant-baseline': 'middle', 'text-anchor': 'end' }, `$${Number(props.current).toFixed(2)}`),
      ])
    }
  },
})

const route = useRoute()
const router = useRouter()

const plan = ref(null)
const savedPlan = ref(null)
const loading = ref(false)
const saving = ref(false)
const savingNotes = ref(false)
const updatingStatus = ref(false)
const error = ref(null)
const notes = ref('')
const needsClosePrice = ref(false)
const closePrice = ref(null)
const pendingStatus = ref(null)

const isPreview = computed(() => !route.params.id)

const availableStatuses = [
  { value: 'active',   label: 'Mark Active',  color: 'blue' },
  { value: 'hit_t1',  label: 'Hit T1',        color: 'green' },
  { value: 'hit_t2',  label: 'Hit T2',        color: 'green' },
  { value: 'stopped', label: 'Stopped Out',   color: 'red' },
  { value: 'expired', label: 'Expired',       color: 'gray' },
  { value: 'cancelled', label: 'Cancel',      color: 'gray' },
]

async function load() {
  loading.value = true
  error.value = null
  try {
    if (isPreview.value) {
      // Generate mode: /plan?ticker=X&signal_type=Y
      const ticker = route.query.ticker
      if (!ticker) throw new Error('No ticker specified')
      const res = await tradesApi.generatePlan(ticker, {
        signal_type: route.query.signal_type || undefined,
        account_value_cad: 7000,
      })
      plan.value = res.data
    } else {
      // Saved plan mode: /trades/:id
      const res = await tradesApi.getPlan(route.params.id)
      savedPlan.value = res.data
      plan.value = res.data
      notes.value = res.data.notes || ''
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load trade plan'
  } finally {
    loading.value = false
  }
}

async function savePlan() {
  saving.value = true
  try {
    const res = await tradesApi.createPlan({
      ticker: plan.value.ticker,
      signal_type: plan.value.signal_type,
      signal_score: plan.value.signal_score,
    })
    // Navigate to the saved plan
    router.replace({ path: `/trades/${res.data.id}` })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save plan'
  } finally {
    saving.value = false
  }
}

async function updateStatus(status) {
  const closingStatuses = ['hit_t1', 'hit_t2', 'stopped']
  if (closingStatuses.includes(status)) {
    needsClosePrice.value = true
    pendingStatus.value = status
    return
  }
  await doUpdateStatus(status, null)
}

async function confirmClose() {
  await doUpdateStatus(pendingStatus.value, closePrice.value)
  needsClosePrice.value = false
  closePrice.value = null
  pendingStatus.value = null
}

async function doUpdateStatus(status, closedPrice) {
  updatingStatus.value = true
  try {
    const body = { status }
    if (closedPrice != null) body.closed_price = closedPrice
    const res = await tradesApi.updateStatus(savedPlan.value.id, body)
    savedPlan.value = res.data
    plan.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to update status'
  } finally {
    updatingStatus.value = false
  }
}

async function saveNotes() {
  savingNotes.value = true
  try {
    const res = await tradesApi.updateNotes(savedPlan.value.id, notes.value)
    savedPlan.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save notes'
  } finally {
    savingNotes.value = false
  }
}

// ── Formatters ────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toFixed(2)
}

function fmtK(n) {
  if (n == null) return '—'
  return Number(n) >= 1000 ? (Number(n) / 1000).toFixed(1) + 'k' : Number(n).toFixed(0)
}

function pct(n) {
  if (n == null) return ''
  return (Number(n) * 100).toFixed(0) + '%'
}

function fromEntry(price) {
  const mid = plan.value?.entry_mid || plan.value?.current_price
  if (!mid) return '—'
  return ((Number(price) - Number(mid)) / Number(mid) * 100).toFixed(1)
}

function rrClass(rr) {
  if (rr >= 2) return 'positive'
  if (rr >= 1.5) return 'warning'
  return 'negative'
}

function formatSignal(type) {
  const map = {
    RSI_PULLBACK: 'RSI Pullback', RSI_REVERSAL: 'RSI Reversal',
    MACD_CROSSOVER: 'MACD Cross', EMA_CROSSOVER: 'EMA Cross',
    BB_BOUNCE: 'BB Bounce', VOLUME_BREAKOUT: 'Vol Breakout', COMBO: 'Combo',
  }
  return map[type] || type
}

function signalClass(type) {
  const map = {
    RSI_PULLBACK: 'sig-blue', RSI_REVERSAL: 'sig-green', MACD_CROSSOVER: 'sig-purple',
    EMA_CROSSOVER: 'sig-teal', BB_BOUNCE: 'sig-yellow', VOLUME_BREAKOUT: 'sig-orange', COMBO: 'sig-accent',
  }
  return map[type] || 'sig-blue'
}

onMounted(load)
</script>

<style scoped>
.trade-plan { max-width: 680px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }

.back-btn {
  align-self: flex-start;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}
.back-btn:hover { color: var(--text); }

/* Loading / error */
.loading-state { text-align: center; padding: 60px 16px; }
.loading-msg { color: var(--text-muted); margin-top: 12px; }
.error-card { text-align: center; }
.retry-btn { margin-top: 12px; background: var(--border); color: var(--text); border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; }

/* Header card */
.plan-header { display: flex; justify-content: space-between; align-items: flex-start; }
.ticker-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.ticker { font-size: 24px; font-weight: 700; }
.exchange-badge { font-size: 11px; background: var(--border); color: var(--text-muted); padding: 2px 6px; border-radius: 4px; }
.currency-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; }
.currency-badge.usd { background: rgba(245,158,11,0.15); color: var(--yellow); border: 1px solid rgba(245,158,11,0.3); }
.currency-badge.cad { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
.sector-badge { font-size: 11px; color: var(--text-muted); background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.25); padding: 2px 6px; border-radius: 4px; }
.plan-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.signal-badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; }
.score-label { font-size: 12px; color: var(--text-muted); }
.status-badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; text-transform: capitalize; }
.status-pending   { background: rgba(59,130,246,0.15); color: #60a5fa; }
.status-active    { background: rgba(34,197,94,0.15); color: var(--green); }
.status-hit_t1    { background: rgba(34,197,94,0.25); color: var(--green); }
.status-hit_t2    { background: rgba(34,197,94,0.35); color: var(--green); }
.status-stopped   { background: rgba(239,68,68,0.15); color: var(--red); }
.status-expired   { background: var(--border); color: var(--text-muted); }
.status-cancelled { background: var(--border); color: var(--text-muted); }
.header-right { text-align: right; }
.current-price { font-size: 22px; font-weight: 700; }
.price-label { font-size: 11px; color: var(--text-muted); }

/* Signal colors */
.sig-blue   { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); }
.sig-green  { background: rgba(34,197,94,0.15);  color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.sig-purple { background: rgba(168,85,247,0.15); color: #c084fc; border: 1px solid rgba(168,85,247,0.3); }
.sig-teal   { background: rgba(20,184,166,0.15); color: #2dd4bf; border: 1px solid rgba(20,184,166,0.3); }
.sig-yellow { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
.sig-orange { background: rgba(249,115,22,0.15); color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
.sig-accent { background: rgba(99,102,241,0.15); color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }

/* Violations */
.violations-card { border-color: rgba(239,68,68,0.4); }
.violations-title { font-size: 13px; font-weight: 700; color: var(--red); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
.violation-row { display: flex; align-items: flex-start; gap: 8px; padding: 6px 0; font-size: 13px; border-top: 1px solid rgba(239,68,68,0.15); }
.violation-icon { color: var(--red); font-weight: 700; flex-shrink: 0; }

/* Warning cards */
.warning-card { background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.3); color: var(--text); font-size: 13px; display: flex; align-items: flex-start; gap: 8px; }
.earnings-warning { background: rgba(99,102,241,0.08); border-color: rgba(99,102,241,0.3); }
.warning-icon { flex-shrink: 0; }

/* Price ladder */
.section-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
.price-ladder { margin-bottom: 16px; }

.level-table { display: flex; flex-direction: column; gap: 6px; }
.level-row { display: flex; align-items: center; gap: 10px; padding: 6px 8px; border-radius: 6px; font-size: 13px; }
.t2-row    { background: rgba(34,197,94,0.08); }
.t1-row    { background: rgba(34,197,94,0.05); }
.entry-row { background: rgba(59,130,246,0.08); }
.stop-row  { background: rgba(239,68,68,0.08); }

.level-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.green-dot { background: var(--green); }
.green-dot.faded { background: rgba(34,197,94,0.5); }
.blue-dot  { background: var(--blue); }
.red-dot   { background: var(--red); }

.level-name  { flex: 1; color: var(--text-muted); }
.level-price { font-weight: 600; min-width: 120px; text-align: right; }
.level-pct   { min-width: 60px; text-align: right; font-size: 12px; }
.muted       { color: var(--text-muted); }

/* Metrics grid */
.metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.metric-card { text-align: center; padding: 14px 10px; }
.metric-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.metric-value { font-size: 22px; font-weight: 700; }
.metric-sub   { font-size: 11px; color: var(--text-muted); margin-top: 3px; }

/* Notes */
.notes-input {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
}
.save-notes-btn {
  margin-top: 8px;
  background: var(--border);
  color: var(--text);
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

/* Action bar */
.action-bar { }
.action-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }
.action-btns { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.action-btn {
  padding: 10px 28px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: opacity 0.2s;
}
.action-btn.primary { background: var(--accent); color: #fff; }
.action-btn:disabled { opacity: 0.5; cursor: default; }
.violation-hint { font-size: 12px; color: var(--red); }

/* Status buttons */
.status-btns { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.status-btn {
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.status-btn-blue:hover,  .status-btn-blue.active  { border-color: #3b82f6; color: #60a5fa; background: rgba(59,130,246,0.1); }
.status-btn-green:hover, .status-btn-green.active  { border-color: var(--green); color: var(--green); background: rgba(34,197,94,0.1); }
.status-btn-red:hover,   .status-btn-red.active    { border-color: var(--red); color: var(--red); background: rgba(239,68,68,0.1); }
.status-btn-gray:hover,  .status-btn-gray.active   { border-color: var(--text-muted); color: var(--text); background: var(--border); }
.status-btn:disabled { opacity: 0.5; cursor: default; }

.close-price-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.label { font-size: 12px; color: var(--text-muted); }
.close-input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  width: 100px;
}
.save-close-btn {
  background: var(--accent);
  color: #fff;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.save-close-btn:disabled { opacity: 0.5; cursor: default; }
</style>
