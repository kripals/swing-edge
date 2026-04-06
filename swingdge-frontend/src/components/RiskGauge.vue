<template>
  <div class="risk-gauge card">
    <h3 class="gauge-title">Portfolio Risk</h3>

    <div v-if="loading" class="gauge-loading">
      <div class="spinner-sm"></div>
    </div>

    <template v-else-if="health">
      <!-- Active trades bar -->
      <div class="gauge-row">
        <span class="gauge-label">Active Trades</span>
        <div class="bar-wrap">
          <div
            class="bar"
            :class="tradeBarClass"
            :style="{ width: tradeBarPct + '%' }"
          ></div>
        </div>
        <span class="gauge-val" :class="tradeBarClass">
          {{ health.active_trade_count }}/{{ health.max_active_trades }}
        </span>
      </div>

      <!-- Open exposure bar -->
      <div class="gauge-row">
        <span class="gauge-label">Open Exposure</span>
        <div class="bar-wrap">
          <div
            class="bar"
            :class="exposureBarClass"
            :style="{ width: Math.min(health.open_exposure_pct, 100) + '%' }"
          ></div>
        </div>
        <span class="gauge-val" :class="exposureBarClass">
          {{ health.open_exposure_pct }}%
        </span>
      </div>

      <!-- Risk at stake bar -->
      <div class="gauge-row">
        <span class="gauge-label">Risk at Stake</span>
        <div class="bar-wrap">
          <div
            class="bar"
            :class="riskBarClass"
            :style="{ width: Math.min(health.risk_at_stake_pct * 10, 100) + '%' }"
          ></div>
        </div>
        <span class="gauge-val" :class="riskBarClass">
          {{ health.risk_at_stake_pct }}%
        </span>
      </div>

      <!-- Stats row -->
      <div class="gauge-stats">
        <div class="gs">
          <div class="gs-val">{{ health.total_closed_trades }}</div>
          <div class="gs-label">Closed</div>
        </div>
        <div class="gs">
          <div class="gs-val" :class="health.win_rate_pct >= 50 ? 'positive' : 'negative'">
            {{ health.win_rate_pct }}%
          </div>
          <div class="gs-label">Win Rate</div>
        </div>
        <div class="gs">
          <div class="gs-val" :class="health.total_realized_pnl >= 0 ? 'positive' : 'negative'">
            {{ health.total_realized_pnl >= 0 ? '+' : '' }}${{ health.total_realized_pnl.toFixed(0) }}
          </div>
          <div class="gs-label">Realized</div>
        </div>
        <div class="gs">
          <div class="gs-val negative">${{ health.max_drawdown_cad.toFixed(0) }}</div>
          <div class="gs-label">Max DD</div>
        </div>
      </div>

      <!-- Warnings -->
      <div v-if="health.warnings.length" class="gauge-warnings">
        <div v-for="w in health.warnings" :key="w" class="gauge-warning">
          ⚠ {{ w }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { portfolioApi } from '../services/api'

const health = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await portfolioApi.getHealth()
    health.value = res.data
  } catch {
    // Non-critical — fail silently
  } finally {
    loading.value = false
  }
}

const tradeBarPct = computed(() => {
  if (!health.value) return 0
  return (health.value.active_trade_count / health.value.max_active_trades) * 100
})

const tradeBarClass = computed(() => {
  const pct = tradeBarPct.value
  if (pct >= 100) return 'bar-red'
  if (pct >= 60) return 'bar-yellow'
  return 'bar-green'
})

const exposureBarClass = computed(() => {
  const pct = health.value?.open_exposure_pct ?? 0
  if (pct >= 50) return 'bar-red'
  if (pct >= 30) return 'bar-yellow'
  return 'bar-green'
})

const riskBarClass = computed(() => {
  const pct = health.value?.risk_at_stake_pct ?? 0
  if (pct >= 5) return 'bar-red'
  if (pct >= 3) return 'bar-yellow'
  return 'bar-green'
})

onMounted(load)
</script>

<style scoped>
.risk-gauge { display: flex; flex-direction: column; gap: 12px; }

.gauge-title {
  font-size: 12px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.06em;
}

.gauge-loading { text-align: center; padding: 16px; }
.spinner-sm {
  width: 20px; height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

.gauge-row { display: flex; align-items: center; gap: 10px; }
.gauge-label { font-size: 12px; color: var(--text-muted); width: 110px; flex-shrink: 0; }
.bar-wrap { flex: 1; background: var(--bg, #0f172a); border-radius: 4px; height: 6px; overflow: hidden; }
.bar { height: 100%; border-radius: 4px; transition: width 0.4s; min-width: 3px; }
.bar-green  { background: var(--green); }
.bar-yellow { background: var(--yellow); }
.bar-red    { background: var(--red); }
.gauge-val { font-size: 12px; font-weight: 600; width: 46px; text-align: right; flex-shrink: 0; }

/* Stats row */
.gauge-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 4px; }
.gs { text-align: center; }
.gs-val { font-size: 16px; font-weight: 700; }
.gs-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }

/* Warnings */
.gauge-warnings { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
.gauge-warning {
  font-size: 11px; color: var(--yellow);
  background: color-mix(in srgb, var(--yellow) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--yellow) 20%, transparent);
  padding: 4px 10px; border-radius: 6px;
}

.positive { color: var(--green); }
.negative { color: var(--red); }
</style>
