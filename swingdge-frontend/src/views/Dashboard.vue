<template>
  <div class="dashboard">
    <!-- Loading state (handles Render cold start) -->
    <div v-if="store.loading" class="loading-state">
      <div class="spinner"></div>
      <p class="loading-msg">Loading portfolio{{ dots }}</p>
      <p class="loading-sub" v-if="slowLoad">Server is waking up — this can take 30-60 seconds on first load</p>
    </div>

    <div v-else-if="store.error" class="error-state card">
      <p class="negative">{{ store.error }}</p>
      <button @click="store.fetchSummary()" class="retry-btn">Retry</button>
    </div>

    <template v-else-if="store.summary">
      <!-- Portfolio Value Header -->
      <div class="header-row">
        <div>
          <div class="total-value">{{ store.formatCad(store.totalValueCad) }}</div>
          <div class="total-pnl" :class="store.totalPnl >= 0 ? 'positive' : 'negative'">
            {{ store.formatCad(store.totalPnl) }} ({{ store.formatPct(store.totalPnlPct) }}) total unrealized
            <InfoTooltip text="Unrealized means paper profit/loss on holdings you still own. It only becomes real money when you sell." />
          </div>
        </div>
        <button @click="store.fetchSummary()" class="refresh-btn" :disabled="store.loading">
          Refresh
        </button>
      </div>

      <!-- Portfolio Snapshot -->
      <div class="snapshot-card card">
        <p v-for="(line, i) in snapshotLines" :key="i" class="snapshot-line">{{ line }}</p>
      </div>

      <!-- Flags / Warnings -->
      <div v-if="store.flags.length" class="flags-row">
        <div v-for="flag in store.flags" :key="flag" class="flag">
          {{ formatFlag(flag) }}
        </div>
      </div>

      <!-- Problem Holdings Alert -->
      <div v-if="store.problemHoldings.length" class="problems-card card">
        <h3 class="section-title warning">Immediate Review Required</h3>
        <div v-for="h in store.problemHoldings" :key="h.id" class="problem-row">
          <span class="ticker">{{ h.ticker }}</span>
          <span :class="h.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'">
            {{ store.formatPct(h.unrealized_pnl_pct) }}
          </span>
          <div class="flag-row">
            <span v-for="f in h.flags" :key="f" class="flag" :class="f.includes('LEVERAGED') ? 'warning' : ''">
              {{ f.replace(/_/g, ' ') }}
            </span>
          </div>
        </div>
      </div>

      <!-- Account Breakdown -->
      <div class="grid-2">
        <div v-for="acc in store.accounts" :key="acc.id" class="card account-card">
          <div class="account-name">{{ acc.name }}</div>
          <div class="account-value">{{ store.formatCad(acc.total_market_value_cad) }}</div>
          <div class="account-pnl" :class="acc.total_unrealized_pnl >= 0 ? 'positive' : 'negative'">
            {{ store.formatCad(acc.total_unrealized_pnl) }} ({{ store.formatPct(acc.total_unrealized_pnl_pct) }})
          </div>
          <div v-if="acc.contribution_room" class="account-meta">
            TFSA room: {{ store.formatCad(acc.contribution_room) }}
            <InfoTooltip text="How much more you can contribute to this TFSA without triggering a tax penalty." position="left" />
          </div>
        </div>
      </div>

      <!-- Sector Weights -->
      <div v-if="Object.keys(store.sectorWeights).length" class="card">
        <h3 class="section-title">
          Sector Allocation
          <InfoTooltip text="How your portfolio is split across industries. Max 30% in any one sector — yellow means you're over the limit and too concentrated." />
        </h3>
        <div class="sector-list">
          <div v-for="(weight, sector) in sortedSectors" :key="sector" class="sector-row">
            <span class="sector-name">{{ sector }}</span>
            <div class="sector-bar-wrap">
              <div class="sector-bar" :style="{ width: weight + '%' }" :class="{ overweight: weight > 30 }"></div>
            </div>
            <span class="sector-pct" :class="{ warning: weight > 30 }">{{ weight }}%</span>
          </div>
        </div>
      </div>

      <!-- Risk Gauge -->
      <RiskGauge />

      <!-- Top Movers -->
      <div class="card">
        <h3 class="section-title">
          Top Movers
          <InfoTooltip text="Your holdings sorted by biggest price move (up or down) today." />
        </h3>
        <div class="holdings-mini">
          <div v-for="h in topMovers" :key="h.id" class="holding-mini-row">
            <span class="ticker">{{ h.ticker }}</span>
            <span class="exchange-badge">{{ h.exchange }}</span>
            <span class="holding-value">{{ store.formatCad(h.market_value_cad) }}</span>
            <span :class="h.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'" class="holding-pnl">
              {{ store.formatPct(h.unrealized_pnl_pct) }}
            </span>
            <span v-if="h.has_fx_cost" class="fx-badge" title="US stock — Wealthsimple charges 1.5% each way to convert CAD↔USD (3% round-trip)">FX</span>
          </div>
        </div>
        <router-link to="/portfolio" class="see-all">See all holdings →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { usePortfolioStore } from '../stores/portfolio'
import RiskGauge from '../components/RiskGauge.vue'
import InfoTooltip from '../components/InfoTooltip.vue'

const store = usePortfolioStore()
const slowLoad = ref(false)
const dots = ref('')

// Animated dots during loading
let dotInterval
onMounted(async () => {
  dotInterval = setInterval(() => {
    dots.value = dots.value.length >= 3 ? '' : dots.value + '.'
  }, 500)

  // Show "server waking up" message after 5 seconds of loading
  setTimeout(() => { if (store.loading) slowLoad.value = true }, 5000)

  await store.fetchSummary()
  clearInterval(dotInterval)
  slowLoad.value = false
})

onUnmounted(() => clearInterval(dotInterval))

const snapshotLines = computed(() => {
  if (!store.summary) return []
  const lines = []
  const holdings = store.allHoldings
  const pnl = store.totalPnl
  const pnlPct = store.totalPnlPct

  // Overall direction
  const dir = pnl >= 0 ? 'up' : 'down'
  const absPnl = store.formatCad(Math.abs(pnl))
  const absPct = Math.abs(pnlPct).toFixed(2)
  lines.push(`Your portfolio is ${dir} ${absPnl} (${absPct}%) in total unrealized ${pnl >= 0 ? 'gains' : 'losses'}.`)

  // Holdings breakdown
  if (holdings.length > 0) {
    const green = holdings.filter(h => h.unrealized_pnl_pct > 0).length
    const red = holdings.filter(h => h.unrealized_pnl_pct < 0).length
    const sorted = [...holdings].sort((a, b) => b.unrealized_pnl_pct - a.unrealized_pnl_pct)
    const best = sorted[0]
    const worst = sorted[sorted.length - 1]
    let line = `${green} of ${holdings.length} holdings are profitable`
    if (red > 0) line += `, ${red} are in the red`
    if (best && worst && best !== worst) {
      line += `. Best: ${best.ticker} (${best.unrealized_pnl_pct > 0 ? '+' : ''}${best.unrealized_pnl_pct.toFixed(1)}%), worst: ${worst.ticker} (${worst.unrealized_pnl_pct.toFixed(1)}%)`
    }
    lines.push(line + '.')
  }

  // Concentration warnings
  const sectorFlags = store.flags.filter(f => f.startsWith('SECTOR_OVERWEIGHT'))
  if (sectorFlags.length) {
    const sectors = sectorFlags.map(f => f.split(':')[1]).join(' and ')
    lines.push(`Concentration warning: ${sectors} sector${sectorFlags.length > 1 ? 's are' : ' is'} over the 30% limit — consider trimming before adding new positions.`)
  }

  // Problem holdings
  if (store.problemHoldings.length > 0) {
    lines.push(`${store.problemHoldings.length} position${store.problemHoldings.length > 1 ? 's require' : ' requires'} immediate review below.`)
  }

  return lines
})

const sortedSectors = computed(() => {
  const weights = store.sectorWeights
  return Object.fromEntries(
    Object.entries(weights).sort(([, a], [, b]) => b - a)
  )
})

const topMovers = computed(() => {
  return [...store.allHoldings]
    .sort((a, b) => Math.abs(b.unrealized_pnl_pct) - Math.abs(a.unrealized_pnl_pct))
    .slice(0, 6)
})

function formatFlag(flag) {
  const map = {
    'SECTOR_OVERWEIGHT': 'Sector overweight',
    'POSITION_OVERWEIGHT': 'Position overweight',
  }
  for (const [key, label] of Object.entries(map)) {
    if (flag.startsWith(key)) {
      const parts = flag.split(':')
      return `${label}: ${parts[1]} ${parts[2]}`
    }
  }
  return flag.replace(/_/g, ' ')
}
</script>

<style scoped>
.dashboard { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

.loading-state { text-align: center; padding: 60px 16px; }
.loading-msg { color: var(--text-muted); margin-top: 12px; }
.loading-sub { color: var(--text-muted); font-size: 12px; margin-top: 8px; max-width: 300px; margin: 8px auto 0; }

.error-state { text-align: center; }
.retry-btn {
  margin-top: 12px;
  background: var(--border);
  color: var(--text);
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.total-value { font-size: 32px; font-weight: 700; }
.total-pnl { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
.refresh-btn {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.snapshot-card { background: color-mix(in srgb, var(--accent) 6%, var(--bg-card)); border-color: color-mix(in srgb, var(--accent) 20%, transparent); }
.snapshot-line { font-size: 13px; color: var(--text); line-height: 1.6; margin: 0; }
.snapshot-line + .snapshot-line { margin-top: 6px; }

.flags-row { display: flex; flex-wrap: wrap; gap: 8px; }

.problems-card { border-color: rgba(239, 68, 68, 0.4); }
.section-title { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; }

.problem-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border); }
.problem-row:last-child { border-bottom: none; }
.flag-row { display: flex; gap: 6px; margin-left: auto; }

.account-card .account-name { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
.account-card .account-value { font-size: 20px; font-weight: 700; }
.account-card .account-pnl { font-size: 13px; margin-top: 2px; }
.account-card .account-meta { font-size: 11px; color: var(--text-muted); margin-top: 8px; }

.sector-list { display: flex; flex-direction: column; gap: 8px; }
.sector-row { display: flex; align-items: center; gap: 10px; }
.sector-name { width: 100px; font-size: 13px; color: var(--text-muted); flex-shrink: 0; }
.sector-bar-wrap { flex: 1; background: var(--bg); border-radius: 4px; height: 8px; overflow: hidden; }
.sector-bar { height: 100%; background: var(--blue); border-radius: 4px; min-width: 4px; transition: width 0.4s; }
.sector-bar.overweight { background: var(--yellow); }
.sector-pct { width: 42px; text-align: right; font-size: 13px; }

.holdings-mini { display: flex; flex-direction: column; gap: 1px; }
.holding-mini-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); }
.holding-mini-row:last-child { border-bottom: none; }
.ticker { font-weight: 600; min-width: 70px; }
.exchange-badge { font-size: 10px; color: var(--text-muted); background: var(--border); padding: 2px 5px; border-radius: 4px; }
.holding-value { margin-left: auto; font-size: 13px; }
.holding-pnl { min-width: 70px; text-align: right; font-size: 13px; font-weight: 600; }
.fx-badge { font-size: 10px; background: rgba(245,158,11,0.15); color: var(--yellow); padding: 2px 5px; border-radius: 4px; border: 1px solid rgba(245,158,11,0.3); }

.see-all { display: block; margin-top: 12px; text-align: right; color: var(--accent); font-size: 13px; text-decoration: none; }
</style>
