<template>
  <div class="holding-card" :class="{ 'has-flags': holding.flags.length }">
    <div class="holding-top">
      <div class="holding-left">
        <span class="ticker">{{ holding.ticker }}</span>
        <span class="exchange-badge">{{ holding.exchange }}</span>
        <span v-if="holding.is_leveraged_etf" class="badge leveraged">3x</span>
        <span v-if="holding.has_fx_cost" class="badge fx">FX -3%</span>
      </div>
      <div class="holding-value">
        {{ formatCad(holding.market_value_cad) }}
      </div>
    </div>

    <div class="holding-details">
      <div class="detail">
        <span class="label">Shares</span>
        <span>{{ holding.shares }}</span>
      </div>
      <div class="detail">
        <span class="label">Avg cost</span>
        <span>{{ formatLocalCurrency(holding.avg_cost, holding.currency) }}</span>
      </div>
      <div class="detail">
        <span class="label">Price</span>
        <span>{{ holding.current_price ? formatLocalCurrency(holding.current_price, holding.currency) : '—' }}</span>
      </div>
      <div class="detail">
        <span class="label">P&amp;L</span>
        <span :class="holding.unrealized_pnl >= 0 ? 'positive' : 'negative'" class="pnl-value">
          {{ formatCad(holding.unrealized_pnl) }}
          ({{ formatPct(holding.unrealized_pnl_pct) }})
        </span>
      </div>
    </div>

    <div v-if="holding.flags.length" class="flags-row">
      <span
        v-for="flag in holding.flags"
        :key="flag"
        class="flag"
        :class="flag.includes('LEVERAGED') || flag.includes('FX') ? 'warning' : ''"
      >
        {{ formatFlag(flag) }}
      </span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  holding: { type: Object, required: true },
})

function formatCad(value) {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 2 }).format(value)
}

function formatLocalCurrency(value, currency) {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency, minimumFractionDigits: 2 }).format(value)
}

function formatPct(value) {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatFlag(flag) {
  const map = {
    'LARGE_LOSS': 'Large loss — review exit',
    'LEVERAGED_ETF': 'Leveraged ETF',
    'CONSIDER_PROFIT_TAKING': 'Consider taking profits',
  }
  if (flag.startsWith('FX_COST_')) return `FX cost: ${flag.split('_').pop()}`
  return map[flag] || flag.replace(/_/g, ' ')
}
</script>

<style scoped>
.holding-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  transition: border-color 0.15s;
}
.holding-card.has-flags {
  border-color: rgba(239, 68, 68, 0.35);
}

.holding-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.holding-left { display: flex; align-items: center; gap: 8px; }
.ticker { font-weight: 700; font-size: 15px; }
.exchange-badge {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
}
.badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}
.badge.leveraged {
  background: rgba(239, 68, 68, 0.15);
  color: var(--red);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.badge.fx {
  background: rgba(245, 158, 11, 0.15);
  color: var(--yellow);
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.holding-value { font-size: 16px; font-weight: 700; }

.holding-details {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.detail { display: flex; flex-direction: column; gap: 2px; }
.label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.pnl-value { font-weight: 600; }

.flags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
</style>
