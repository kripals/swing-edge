<template>
  <div class="alerts-page">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">Alerts</h1>
          <p class="page-sub">Notification history and test controls.</p>
        </div>
        <button class="test-btn" :disabled="testing" @click="sendTest">
          {{ testing ? 'Sending…' : 'Send Test Alert' }}
        </button>
      </div>
    </div>

    <!-- Test result banner -->
    <div v-if="testResult" class="test-banner" :class="testResult.ok ? 'success' : 'error'">
      {{ testResult.ok ? '✓ Test alert sent to Telegram' : '✗ Failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID' }}
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
      </button>
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

    <!-- Empty -->
    <div v-else-if="!filteredAlerts.length" class="empty-card card">
      <p>No alerts yet.</p>
      <p class="sub">Alerts are sent automatically during market hours and stored here.</p>
    </div>

    <!-- Alert list -->
    <div v-else class="alert-list card">
      <div
        v-for="alert in filteredAlerts"
        :key="alert.id"
        class="alert-row"
        :class="[`priority-${alert.priority}`, { acknowledged: alert.acknowledged }]"
      >
        <div class="alert-left">
          <span class="alert-type-badge" :class="typeBadgeClass(alert.type)">
            {{ typeLabel(alert.type) }}
          </span>
          <span v-if="alert.ticker" class="alert-ticker">{{ alert.ticker }}</span>
        </div>
        <div class="alert-message">{{ alert.message }}</div>
        <div class="alert-meta">
          <span class="alert-time">{{ fmtTime(alert.sent_at) }}</span>
          <span v-if="alert.sent_via" class="alert-via">via {{ alert.sent_via }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { alertsApi } from '../services/api'

const loading = ref(false)
const error = ref(null)
const alerts = ref([])
const activeFilter = ref('all')
const testing = ref(false)
const testResult = ref(null)

const filters = [
  { label: 'All', value: 'all' },
  { label: 'Entry', value: 'entry_signal' },
  { label: 'Stop Hit', value: 'stop_hit' },
  { label: 'Targets', value: 'targets' },
  { label: 'Earnings', value: 'earnings_warning' },
  { label: 'Summary', value: 'summary' },
]

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await alertsApi.getAlerts()
    alerts.value = res.data.alerts
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load alerts'
  } finally {
    loading.value = false
  }
}

async function sendTest() {
  testing.value = true
  testResult.value = null
  try {
    const res = await alertsApi.sendTest()
    testResult.value = { ok: res.data.sent }
    // Refresh list after test
    await load()
  } catch {
    testResult.value = { ok: false }
  } finally {
    testing.value = false
    setTimeout(() => { testResult.value = null }, 5000)
  }
}

const filteredAlerts = computed(() => {
  if (activeFilter.value === 'all') return alerts.value
  if (activeFilter.value === 'targets') {
    return alerts.value.filter(a => a.type === 'target_1_hit' || a.type === 'target_2_hit')
  }
  if (activeFilter.value === 'summary') {
    return alerts.value.filter(a => a.type === 'daily_summary' || a.type === 'morning_briefing')
  }
  return alerts.value.filter(a => a.type === activeFilter.value)
})

function typeLabel(type) {
  const map = {
    entry_signal: 'Entry',
    stop_approaching: 'Stop ⚠',
    stop_hit: 'Stop Hit',
    target_1_hit: 'T1 ✓',
    target_2_hit: 'T2 ✓',
    earnings_warning: 'Earnings',
    daily_summary: 'Summary',
    morning_briefing: 'Briefing',
    scan_complete: 'Scan',
  }
  return map[type] || type
}

function typeBadgeClass(type) {
  if (type === 'stop_hit') return 'badge-red'
  if (type === 'stop_approaching') return 'badge-orange'
  if (type === 'entry_signal') return 'badge-blue'
  if (type === 'target_1_hit' || type === 'target_2_hit') return 'badge-green'
  if (type === 'earnings_warning') return 'badge-yellow'
  return 'badge-grey'
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  if (isToday) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<style scoped>
.alerts-page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

.page-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.page-sub { font-size: 13px; color: var(--text-muted); }

.header-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }

.test-btn {
  padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
  background: var(--accent); color: #fff; border: none; cursor: pointer;
  white-space: nowrap;
}
.test-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* Test result banner */
.test-banner {
  padding: 10px 16px; border-radius: 8px; font-size: 13px; font-weight: 500;
}
.test-banner.success { background: color-mix(in srgb, var(--green) 15%, transparent); color: var(--green); }
.test-banner.error   { background: color-mix(in srgb, var(--red) 15%, transparent); color: var(--red); }

/* Filter chips */
.filter-row { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); cursor: pointer;
}
.chip.active { background: var(--accent); border-color: var(--accent); color: #fff; }

/* Loading / error / empty */
.loading-state { text-align: center; padding: 40px 16px; }
.error-card { text-align: center; padding: 32px 16px; }
.retry-btn { margin-top: 12px; background: var(--border); color: var(--text); border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; }
.empty-card { text-align: center; padding: 40px 16px; }
.empty-card p { color: var(--text-muted); font-size: 14px; }
.empty-card .sub { font-size: 12px; margin-top: 6px; }

/* Alert list */
.alert-list { padding: 0; overflow: hidden; }

.alert-row {
  display: grid;
  grid-template-columns: 200px 1fr auto;
  align-items: start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.alert-row:last-child { border-bottom: none; }
.alert-row.acknowledged { opacity: 0.5; }

/* Priority left border */
.alert-row.priority-critical { border-left: 3px solid var(--red); }
.alert-row.priority-high     { border-left: 3px solid var(--yellow); }
.alert-row.priority-medium   { border-left: 3px solid var(--border); }
.alert-row.priority-low      { border-left: 3px solid transparent; }

.alert-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.alert-ticker { font-weight: 700; font-size: 13px; }

/* Type badges */
.alert-type-badge {
  font-size: 10px; font-weight: 700; padding: 2px 7px;
  border-radius: 4px; text-transform: uppercase; letter-spacing: 0.04em;
  white-space: nowrap;
}
.badge-red    { background: color-mix(in srgb, var(--red) 20%, transparent); color: var(--red); }
.badge-orange { background: color-mix(in srgb, var(--yellow) 20%, transparent); color: var(--yellow); }
.badge-green  { background: color-mix(in srgb, var(--green) 20%, transparent); color: var(--green); }
.badge-blue   { background: color-mix(in srgb, var(--accent) 20%, transparent); color: var(--accent); }
.badge-yellow { background: color-mix(in srgb, var(--yellow) 20%, transparent); color: var(--yellow); }
.badge-grey   { background: var(--surface-2, var(--border)); color: var(--text-muted); }

.alert-message {
  font-size: 12px; color: var(--text-muted);
  white-space: pre-wrap; word-break: break-word;
  /* Strip HTML tags for display */
  line-height: 1.5;
}

.alert-meta { text-align: right; white-space: nowrap; }
.alert-time { font-size: 11px; color: var(--text-muted); display: block; }
.alert-via  { font-size: 10px; color: var(--text-muted); opacity: 0.6; margin-top: 2px; display: block; }

.negative { color: var(--red); }

@media (max-width: 640px) {
  .alert-row { grid-template-columns: 1fr; gap: 6px; }
  .alert-meta { text-align: left; }
  .header-row { flex-direction: column; }
}
</style>
