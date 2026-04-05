<template>
  <div class="settings">
    <div class="page-header">
      <h1 class="page-title">Settings</h1>
      <p class="page-sub">Trading rules loaded from database. Locked rules are hardcoded safety constraints.</p>
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
      <div v-for="group in groups" :key="group.label" class="rule-group card">
        <h2 class="group-title">{{ group.label }}</h2>

        <div
          v-for="rule in group.rules"
          :key="rule.rule_key"
          class="rule-row"
          :class="{ locked: !rule.is_editable }"
        >
          <div class="rule-info">
            <div class="rule-key">{{ formatKey(rule.rule_key) }}</div>
            <div class="rule-desc">{{ rule.description }}</div>
          </div>

          <div class="rule-control">
            <!-- Locked rule — read-only display -->
            <template v-if="!rule.is_editable">
              <span class="rule-value-static">{{ displayValue(rule) }}</span>
              <span class="lock-icon" title="Hardcoded safety rule — cannot be changed via UI">🔒</span>
            </template>

            <!-- Bool toggle -->
            <template v-else-if="rule.value_type === 'bool' || rule.value_type === 'boolean'">
              <label class="toggle">
                <input
                  type="checkbox"
                  :checked="rule.rule_value === 'true' || rule.rule_value === '1'"
                  @change="(e) => save(rule, e.target.checked ? 'true' : 'false')"
                />
                <span class="toggle-track"></span>
              </label>
            </template>

            <!-- Number input -->
            <template v-else>
              <div class="input-group">
                <input
                  type="number"
                  class="rule-input"
                  :value="rule.rule_value"
                  :step="rule.value_type === 'int' || rule.value_type === 'integer' ? 1 : 0.1"
                  :class="{ saving: savingKey === rule.rule_key, saved: savedKey === rule.rule_key, error: errorKey === rule.rule_key }"
                  @blur="(e) => onBlur(rule, e.target.value)"
                  @keydown.enter="(e) => { e.target.blur() }"
                />
                <span class="unit-label">{{ unitLabel(rule.rule_key) }}</span>
              </div>
            </template>

            <!-- Save feedback -->
            <span v-if="savingKey === rule.rule_key" class="feedback saving-text">saving…</span>
            <span v-else-if="savedKey === rule.rule_key" class="feedback saved-text">saved</span>
            <span v-else-if="errorKey === rule.rule_key" class="feedback error-text">{{ saveError }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '../services/api'

const rules = ref([])
const loading = ref(false)
const error = ref(null)
const savingKey = ref(null)
const savedKey = ref(null)
const errorKey = ref(null)
const saveError = ref(null)

// ── Grouping ──────────────────────────────────────────────────────────────────

const GROUP_ORDER = [
  { label: 'Risk Management',   prefixes: ['risk_', 'min_risk', 'max_active', 'trade_expiry'] },
  { label: 'Position Limits',   prefixes: ['max_position', 'max_sector'] },
  { label: 'FX',                prefixes: ['fx_'] },
  { label: 'Earnings',          prefixes: ['earnings_'] },
  { label: 'Scanner Filters',   prefixes: ['scanner_'] },
  { label: 'Trade Plan',        prefixes: ['atr_', 'entry_zone'] },
]

const groups = computed(() => {
  const assigned = new Set()
  const result = []

  for (const g of GROUP_ORDER) {
    const matching = rules.value.filter((r) => {
      if (assigned.has(r.rule_key)) return false
      return g.prefixes.some((p) => r.rule_key.startsWith(p))
    })
    if (matching.length) {
      matching.forEach((r) => assigned.add(r.rule_key))
      result.push({ label: g.label, rules: matching })
    }
  }

  // Catch-all for anything unmatched
  const rest = rules.value.filter((r) => !assigned.has(r.rule_key))
  if (rest.length) result.push({ label: 'Other', rules: rest })

  return result
})

// ── Data fetching ─────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await settingsApi.getRules()
    rules.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load settings'
  } finally {
    loading.value = false
  }
}

// ── Saving ────────────────────────────────────────────────────────────────────

async function save(rule, newValue) {
  if (newValue === rule.rule_value) return
  savingKey.value = rule.rule_key
  savedKey.value = null
  errorKey.value = null
  saveError.value = null

  try {
    const res = await settingsApi.updateRule(rule.rule_key, newValue)
    // Update local state
    const idx = rules.value.findIndex((r) => r.rule_key === rule.rule_key)
    if (idx !== -1) rules.value[idx] = res.data

    savedKey.value = rule.rule_key
    setTimeout(() => {
      if (savedKey.value === rule.rule_key) savedKey.value = null
    }, 2000)
  } catch (e) {
    errorKey.value = rule.rule_key
    saveError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    savingKey.value = null
  }
}

function onBlur(rule, value) {
  if (value !== rule.rule_value) {
    save(rule, value)
  }
}

// ── Formatters ────────────────────────────────────────────────────────────────

function formatKey(key) {
  return key
    .replace(/_pct$/, '')
    .replace(/_cad$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bRsi\b/, 'RSI')
    .replace(/\bAtr\b/, 'ATR')
    .replace(/\bFx\b/, 'FX')
}

function displayValue(rule) {
  if (rule.value_type === 'bool' || rule.value_type === 'boolean') {
    return rule.rule_value === 'true' || rule.rule_value === '1' ? 'Enabled' : 'Disabled'
  }
  const unit = unitLabel(rule.rule_key)
  return unit ? `${rule.rule_value} ${unit}` : rule.rule_value
}

function unitLabel(key) {
  if (key.endsWith('_pct') || key.includes('_pct_')) return '%'
  if (key.endsWith('_days')) return 'days'
  if (key.endsWith('_trades')) return 'trades'
  if (key.includes('market_cap')) return 'CAD'
  if (key.includes('multiplier')) return '×'
  return ''
}

onMounted(load)
</script>

<style scoped>
.settings { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

.page-header { }
.page-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.page-sub { font-size: 13px; color: var(--text-muted); }

/* Loading / error */
.loading-state { text-align: center; padding: 40px 16px; }
.error-card { text-align: center; }
.retry-btn { margin-top: 12px; background: var(--border); color: var(--text); border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; }

/* Group */
.rule-group { display: flex; flex-direction: column; gap: 0; }
.group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}

/* Rule row */
.rule-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}
.rule-row.locked { opacity: 0.7; }

.rule-info { flex: 1; min-width: 0; }
.rule-key  { font-size: 13px; font-weight: 600; }
.rule-desc { font-size: 12px; color: var(--text-muted); margin-top: 2px; line-height: 1.4; }

.rule-control {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Read-only */
.rule-value-static { font-size: 14px; font-weight: 600; color: var(--text-muted); }
.lock-icon { font-size: 13px; opacity: 0.6; }

/* Number input */
.input-group { display: flex; align-items: center; gap: 4px; }
.rule-input {
  width: 80px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  text-align: right;
  transition: border-color 0.2s;
}
.rule-input:focus { outline: none; border-color: var(--accent); }
.rule-input.saving { border-color: var(--yellow); }
.rule-input.saved  { border-color: var(--green); }
.rule-input.error  { border-color: var(--red); }
.unit-label { font-size: 12px; color: var(--text-muted); min-width: 28px; }

/* Toggle */
.toggle { position: relative; display: inline-block; cursor: pointer; }
.toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
.toggle-track {
  display: block;
  width: 40px;
  height: 22px;
  background: var(--border);
  border-radius: 11px;
  transition: background 0.2s;
  position: relative;
}
.toggle-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}
.toggle input:checked + .toggle-track { background: var(--accent); }
.toggle input:checked + .toggle-track::after { transform: translateX(18px); background: #fff; }

/* Feedback labels */
.feedback { font-size: 11px; min-width: 44px; }
.saving-text { color: var(--yellow); }
.saved-text  { color: var(--green); }
.error-text  { color: var(--red); }
</style>
