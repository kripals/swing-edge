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
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { usePortfolioStore } from '../stores/portfolio'
import HoldingCard from '../components/HoldingCard.vue'

const store = usePortfolioStore()

onMounted(() => {
  if (!store.summary) store.fetchSummary()
})

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
</style>
