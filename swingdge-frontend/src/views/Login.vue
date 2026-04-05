<template>
  <div class="login-wrap">
    <div class="login-card card">
      <h1 class="login-title">SwingEdge</h1>
      <p class="login-sub">Swing trading research &amp; portfolio tracker</p>

      <form @submit.prevent="login">
        <div class="field">
          <label>Password</label>
          <input
            v-model="password"
            type="password"
            placeholder="Enter your password"
            :disabled="loading"
            autofocus
          />
        </div>
        <p v-if="error" class="error-msg">{{ error }}</p>
        <button type="submit" :disabled="loading || !password" class="btn-primary">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../services/api'

const router = useRouter()
const password = ref('')
const loading = ref(false)
const error = ref('')

async function login() {
  loading.value = true
  error.value = ''
  try {
    const resp = await authApi.login(password.value)
    localStorage.setItem('swingdge_token', resp.data.access_token)
    router.push('/')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.login-card {
  width: 100%;
  max-width: 360px;
}
.login-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
  text-align: center;
  margin-bottom: 4px;
}
.login-sub {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 24px;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.field input {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  color: var(--text);
  font-size: 14px;
  outline: none;
}
.field input:focus {
  border-color: var(--accent);
}
.btn-primary {
  width: 100%;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.error-msg {
  color: var(--red);
  font-size: 13px;
  margin-bottom: 12px;
}
</style>
