<template>
  <div class="market">
    <div class="page-header">
      <h1 class="page-title">Market</h1>
      <p class="page-sub">Macro snapshot, sector rotation, and earnings calendar.</p>
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

    <template v-else>
      <!-- ── Macro snapshot ─────────────────────────────────────────────── -->
      <section class="section">
        <h2 class="section-title">Macro</h2>
        <div class="macro-grid">
          <!-- BoC metrics -->
          <div
            v-for="metric in macroMetrics"
            :key="metric.key"
            class="macro-card card"
          >
            <div class="macro-label">{{ metric.label }}</div>
            <div class="macro-val" :class="metric.colorClass">
              {{ metric.display }}
            </div>
            <div v-if="metric.date" class="macro-date">{{ metric.date }}</div>
          </div>
        </div>
      </section>

      <!-- ── Commodities ───────────────────────────────────────────────── -->
      <section class="section">
        <h2 class="section-title">Commodities</h2>
        <div class="commodity-row card">
          <div
            v-for="c in commodities"
            :key="c.key"
            class="commodity-item"
          >
            <div class="commodity-label">{{ c.label }}</div>
            <div class="commodity-val">
              {{ c.value != null ? `$${Number(c.value).toFixed(2)}` : '—' }}
            </div>
            <div class="commodity-unit">{{ c.unit }}</div>
          </div>
        </div>
      </section>

      <!-- ── Sector Heatmap ────────────────────────────────────────────── -->
      <section class="section">
        <h2 class="section-title">Sector Rotation</h2>
        <div v-if="sectorsLoading" class="loading-inline">Loading sectors…</div>
        <div v-else-if="sectors.length" class="sector-grid">
          <div
            v-for="s in sectors"
            :key="s.ticker"
            class="sector-tile"
            :class="sectorTileClass(s.change_pct)"
            :title="s.name"
          >
            <div class="sector-name">{{ s.sector }}</div>
            <div class="sector-ticker">{{ s.ticker }}</div>
            <div class="sector-change" :class="s.change_pct >= 0 ? 'positive' : 'negative'">
              {{ s.change_pct != null ? `${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%` : '—' }}
            </div>
            <div v-if="s.price" class="sector-price">${{ s.price.toFixed(2) }}</div>
          </div>
        </div>
        <div v-else class="empty-inline">No sector data available.</div>
      </section>

      <!-- ── Earnings Countdown ────────────────────────────────────────── -->
      <section class="section">
        <h2 class="section-title">Earnings Countdown</h2>
        <p class="section-sub">Holdings and watchlist tickers with upcoming earnings.</p>
        <div v-if="earningsLoading" class="loading-inline">Loading earnings…</div>
        <div v-else-if="earningsItems.length" class="earnings-list card">
          <div
            v-for="item in earningsItems"
            :key="item.ticker"
            class="earnings-row"
            :class="{ 'in-blackout': item.days_away <= 5 }"
          >
            <div class="earnings-ticker">{{ item.ticker }}</div>
            <div class="earnings-right">
              <span
                class="days-badge"
                :class="item.days_away <= 5 ? 'danger' : item.days_away <= 14 ? 'warning' : 'ok'"
              >
                {{ item.days_away }}d
              </span>
              <span class="earnings-date">{{ item.date }}</span>
              <span v-if="item.days_away <= 5" class="blackout-label">BLACKOUT</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-inline card">No upcoming earnings in the next 30 days.</div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { marketApi } from '../services/api'

const loading = ref(false)
const error = ref(null)
const macro = ref(null)

const sectorsLoading = ref(false)
const sectors = ref([])

const earningsLoading = ref(false)
const earningsItems = ref([])

// Tickers to check for earnings: holdings + common watchlist
const EARNINGS_TICKERS = [
  'RY.TO', 'TD.TO', 'BNS.TO', 'BMO.TO', 'CM.TO',
  'SU.TO', 'CNQ.TO', 'ENB.TO', 'TRP.TO',
  'SHOP.TO', 'CNR.TO', 'CP.TO', 'ATD.TO',
  'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META',
  'JPM', 'BAC', 'XOM', 'CVX',
]

// ── Loaders ───────────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await marketApi.getMacro()
    macro.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load macro data'
  } finally {
    loading.value = false
  }

  // Load sectors and earnings in parallel after macro
  loadSectors()
  loadEarnings()
}

async function loadSectors() {
  sectorsLoading.value = true
  try {
    const res = await marketApi.getSectors()
    sectors.value = res.data
  } catch {
    sectors.value = []
  } finally {
    sectorsLoading.value = false
  }
}

async function loadEarnings() {
  earningsLoading.value = true
  const results = []
  // Fetch a few tickers concurrently in small batches
  const BATCH = 5
  for (let i = 0; i < EARNINGS_TICKERS.length; i += BATCH) {
    const batch = EARNINGS_TICKERS.slice(i, i + BATCH)
    const settled = await Promise.allSettled(
      batch.map((t) => marketApi.getEarnings(t))
    )
    for (const r of settled) {
      if (r.status === 'fulfilled' && r.value.data?.next_earnings_date) {
        const d = r.value.data
        if (d.earnings_days_away != null && d.earnings_days_away <= 30) {
          results.push({
            ticker: d.ticker,
            days_away: d.earnings_days_away,
            date: d.next_earnings_date,
          })
        }
      }
    }
  }
  results.sort((a, b) => a.days_away - b.days_away)
  earningsItems.value = results
  earningsLoading.value = false
}

// ── Computed ──────────────────────────────────────────────────────────────────

const macroMetrics = computed(() => {
  if (!macro.value) return []
  const m = macro.value
  return [
    {
      key: 'overnight',
      label: 'BoC Overnight Rate',
      display: m.overnight_rate ? `${m.overnight_rate.value}%` : '—',
      date: m.overnight_rate?.date,
      colorClass: m.overnight_rate ? (m.overnight_rate.value >= 4 ? 'negative' : 'positive') : '',
    },
    {
      key: 'usd_cad',
      label: 'USD/CAD',
      display: m.usd_cad ? m.usd_cad.value.toFixed(4) : '—',
      date: m.usd_cad?.date,
      colorClass: '',
    },
    {
      key: 'cpi',
      label: 'CPI (Canada)',
      display: m.cpi ? m.cpi.value.toFixed(1) : '—',
      date: m.cpi?.date,
      colorClass: '',
    },
  ]
})

const commodities = computed(() => {
  if (!macro.value?.commodities) return []
  const c = macro.value.commodities
  return [
    { key: 'wti',     label: 'WTI Oil',     value: c.wti_oil?.value,     unit: 'USD/bbl'   },
    { key: 'gold',    label: 'Gold',         value: c.gold?.value,        unit: 'USD/oz'    },
    { key: 'natgas',  label: 'Nat. Gas',     value: c.natural_gas?.value, unit: 'USD/MMBtu' },
    { key: 'copper',  label: 'Copper',       value: c.copper?.value,      unit: 'USD/lb'    },
  ]
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function sectorTileClass(changePct) {
  if (changePct == null) return 'neutral'
  if (changePct >= 1.5)  return 'strong-up'
  if (changePct >= 0.5)  return 'mild-up'
  if (changePct >= -0.5) return 'flat'
  if (changePct >= -1.5) return 'mild-down'
  return 'strong-down'
}

onMounted(load)
</script>

<style scoped>
.market { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }

.page-header {}
.page-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.page-sub { font-size: 13px; color: var(--text-muted); }

/* Loading / error */
.loading-state { text-align: center; padding: 40px 16px; }
.error-card { text-align: center; padding: 32px 16px; }
.retry-btn { margin-top: 12px; background: var(--border); color: var(--text); border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; }
.loading-inline { font-size: 13px; color: var(--text-muted); padding: 8px 0; }
.empty-inline { font-size: 13px; color: var(--text-muted); padding: 16px; text-align: center; }

/* Sections */
.section { display: flex; flex-direction: column; gap: 12px; }
.section-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.section-sub { font-size: 12px; color: var(--text-muted); margin-top: -8px; }

/* Macro grid */
.macro-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.macro-card { padding: 16px; display: flex; flex-direction: column; gap: 4px; }
.macro-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.macro-val { font-size: 24px; font-weight: 700; }
.macro-date { font-size: 11px; color: var(--text-muted); }

/* Commodities */
.commodity-row { display: flex; gap: 0; padding: 0; overflow: hidden; }
.commodity-item {
  flex: 1; text-align: center; padding: 16px 8px;
  border-right: 1px solid var(--border);
}
.commodity-item:last-child { border-right: none; }
.commodity-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.commodity-val { font-size: 18px; font-weight: 700; margin-top: 4px; }
.commodity-unit { font-size: 10px; color: var(--text-muted); margin-top: 2px; }

/* Sector heatmap */
.sector-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.sector-tile {
  padding: 14px 12px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  border: 1px solid transparent;
}
.sector-name   { font-size: 12px; font-weight: 600; }
.sector-ticker { font-size: 10px; opacity: 0.7; }
.sector-change { font-size: 16px; font-weight: 700; margin-top: 4px; }
.sector-price  { font-size: 11px; opacity: 0.7; }

/* Tile color states */
.sector-tile.strong-up  { background: color-mix(in srgb, var(--green) 25%, transparent); border-color: color-mix(in srgb, var(--green) 30%, transparent); }
.sector-tile.mild-up    { background: color-mix(in srgb, var(--green) 12%, transparent); border-color: color-mix(in srgb, var(--green) 15%, transparent); }
.sector-tile.flat       { background: var(--surface); border-color: var(--border); }
.sector-tile.mild-down  { background: color-mix(in srgb, var(--red) 12%, transparent); border-color: color-mix(in srgb, var(--red) 15%, transparent); }
.sector-tile.strong-down{ background: color-mix(in srgb, var(--red) 25%, transparent); border-color: color-mix(in srgb, var(--red) 30%, transparent); }
.sector-tile.neutral    { background: var(--surface); border-color: var(--border); }

/* Earnings countdown */
.earnings-list { padding: 0; overflow: hidden; }
.earnings-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.earnings-row:last-child { border-bottom: none; }
.earnings-row.in-blackout { background: color-mix(in srgb, var(--red) 6%, transparent); }
.earnings-ticker { font-size: 14px; font-weight: 700; }
.earnings-right { display: flex; align-items: center; gap: 10px; }
.earnings-date { font-size: 12px; color: var(--text-muted); }
.blackout-label { font-size: 10px; font-weight: 700; color: var(--red); letter-spacing: 0.06em; }

.days-badge {
  font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 4px;
  min-width: 36px; text-align: center;
}
.days-badge.danger  { background: color-mix(in srgb, var(--red) 20%, transparent); color: var(--red); }
.days-badge.warning { background: color-mix(in srgb, var(--yellow) 20%, transparent); color: var(--yellow); }
.days-badge.ok      { background: color-mix(in srgb, var(--green) 15%, transparent); color: var(--green); }

/* Shared */
.positive { color: var(--green); }
.negative { color: var(--red); }

@media (max-width: 640px) {
  .macro-grid { grid-template-columns: repeat(2, 1fr); }
  .sector-grid { grid-template-columns: repeat(2, 1fr); }
  .commodity-row { flex-wrap: wrap; }
  .commodity-item { flex: 1 1 50%; border-right: none; border-bottom: 1px solid var(--border); }
}
</style>
