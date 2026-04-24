<template>
  <div id="app">
    <!-- Nav bar (hidden on login screen) -->
    <nav v-if="isAuthenticated" class="nav">
      <router-link to="/" class="nav-brand">SwingEdge</router-link>
      <div class="nav-links">
        <router-link to="/">Dashboard</router-link>
        <router-link to="/portfolio">Portfolio</router-link>
        <router-link to="/scanner">Scanner</router-link>
        <router-link to="/market">Market</router-link>
        <router-link to="/history">History</router-link>
        <router-link to="/alerts">Alerts</router-link>
        <router-link to="/chat">AI Chat</router-link>
        <router-link to="/settings">Settings</router-link>
      </div>
    </nav>

    <!-- Cold start banner -->
    <div v-if="showColdStartBanner" class="cold-start-banner">
      Server waking up — first load may take 30-60 seconds...
    </div>

    <main :class="{ 'with-nav': isAuthenticated }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isAuthenticated = computed(() => !!localStorage.getItem('swingdge_token'))
const showColdStartBanner = ref(false)

// Show cold start banner when API responds with X-Cold-Start: true
// (The portfolio store sets isColdStart — we listen for route changes to check)
</script>

<style>
:root {
  --bg: #0f172a;
  --bg-card: #1e293b;
  --border: #334155;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --green: #22c55e;
  --red: #ef4444;
  --yellow: #f59e0b;
  --blue: #3b82f6;
  --accent: #6366f1;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

#app { min-height: 100vh; }

.nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 52px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 24px;
  z-index: 100;
}

.nav-brand {
  font-weight: 700;
  font-size: 16px;
  color: var(--accent);
  text-decoration: none;
}

.nav-links {
  display: flex;
  gap: 16px;
}

.nav-links a {
  color: var(--text-muted);
  text-decoration: none;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--text);
  background: var(--border);
}

.cold-start-banner {
  position: fixed;
  top: 52px;
  left: 0;
  right: 0;
  background: var(--yellow);
  color: #000;
  text-align: center;
  padding: 6px;
  font-size: 13px;
  z-index: 99;
}

main {
  padding: 16px;
  min-height: 100vh;
}

main.with-nav {
  padding-top: 68px;
  min-height: calc(100vh - 52px);
}

/* Card */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
}

/* Value colors */
.positive { color: var(--green); }
.negative { color: var(--red); }
.warning  { color: var(--yellow); }

/* Grid helpers */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }

/* Loading spinner */
.spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 40px auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Flag badge */
.flag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(239, 68, 68, 0.15);
  color: var(--red);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.flag.warning {
  background: rgba(245, 158, 11, 0.15);
  color: var(--yellow);
  border-color: rgba(245, 158, 11, 0.3);
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .nav { padding: 0 10px; gap: 12px; overflow-x: auto; }
  .nav-links { gap: 4px; }
  .nav-links a { padding: 4px 6px; font-size: 12px; }
  .nav-brand { font-size: 14px; flex-shrink: 0; }
  main { padding: 12px; }
  main.with-nav { padding-top: 64px; }
  .grid-2 { grid-template-columns: 1fr; }
  .grid-3 { grid-template-columns: 1fr 1fr; }
}
</style>
