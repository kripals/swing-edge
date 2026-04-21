<template>
  <div class="chat-page">
    <div class="chat-header">
      <h1 class="chat-title">AI Stock Advisor</h1>
      <p class="chat-sub">Ask anything about your portfolio or a specific stock</p>
    </div>

    <!-- Quick action chips -->
    <div class="quick-actions">
      <button
        v-for="q in quickActions"
        :key="q.label"
        class="quick-chip"
        :disabled="loading"
        @click="sendQuick(q.message)"
      >
        {{ q.label }}
      </button>
    </div>

    <!-- Message thread -->
    <div class="chat-thread" ref="threadEl">
      <div v-if="messages.length === 0 && !loading" class="chat-empty">
        No messages yet. Ask something above or use a quick action.
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id ?? msg._key"
        class="msg-group"
      >
        <!-- User bubble -->
        <div class="bubble-row user-row">
          <div class="bubble bubble-user">{{ msg.user_message }}</div>
        </div>

        <!-- AI bubble -->
        <div class="bubble-row ai-row">
          <div class="bubble bubble-ai">
            <span v-if="msg.ticker" class="ticker-badge">{{ msg.ticker }}</span>
            <span class="context-badge" :class="'ctx-' + msg.context_used">{{ msg.context_used }}</span>
            <div class="ai-text">{{ msg.ai_reply }}</div>
          </div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="loading" class="bubble-row ai-row">
        <div class="bubble bubble-ai typing">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="chat-error">{{ error }}</div>

    <!-- Input bar -->
    <div class="input-bar">
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="Ask about your portfolio, a stock, or anything trading-related…"
        :disabled="loading"
        @keydown.enter.prevent="send"
      />
      <button class="send-btn" :disabled="loading || !inputText.trim()" @click="send">
        {{ loading ? '…' : 'Send' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { chatApi } from '../services/api'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const error = ref(null)
const threadEl = ref(null)

const quickActions = [
  { label: 'Study my whole portfolio', message: 'Study my whole portfolio and give me a summary of what I should be paying attention to.' },
  { label: 'What should I sell?', message: 'Which of my holdings should I consider selling right now and why?' },
  { label: 'Strongest holding?', message: 'Which stock in my portfolio has the strongest momentum right now?' },
  { label: 'Biggest risks?', message: 'What are the biggest risks in my portfolio right now?' },
]

onMounted(async () => {
  try {
    const res = await chatApi.getHistory()
    messages.value = res.data
    await scrollToBottom()
  } catch {
    // No history yet — fine
  }
})

async function send() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  inputText.value = ''
  error.value = null
  loading.value = true

  // Optimistic: show user message immediately
  const tempKey = Date.now()
  const optimistic = { _key: tempKey, user_message: text, ai_reply: '', ticker: null, context_used: 'portfolio' }
  messages.value.push(optimistic)
  await scrollToBottom()

  try {
    const res = await chatApi.send(text)
    // Replace optimistic entry with real response
    const idx = messages.value.findIndex(m => m._key === tempKey)
    if (idx !== -1) {
      messages.value[idx] = { ...res.data, _key: tempKey }
    }
  } catch (e) {
    const idx = messages.value.findIndex(m => m._key === tempKey)
    if (idx !== -1) messages.value.splice(idx, 1)
    if (e.response?.status === 503) {
      error.value = 'AI chat is not configured yet — ANTHROPIC_API_KEY missing on the server.'
    } else {
      error.value = 'Failed to get a response. Please try again.'
    }
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function sendQuick(message) {
  inputText.value = message
  await send()
}

async function scrollToBottom() {
  await nextTick()
  if (threadEl.value) {
    threadEl.value.scrollTop = threadEl.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-page {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 84px);
}

.chat-header { flex-shrink: 0; }
.chat-title { font-size: 20px; font-weight: 700; }
.chat-sub { font-size: 13px; color: var(--text-muted); margin-top: 2px; }

/* Quick actions */
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}
.quick-chip {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.quick-chip:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--accent);
}
.quick-chip:disabled { opacity: 0.4; cursor: not-allowed; }

/* Thread */
.chat-thread {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 4px;
  min-height: 0;
}

.chat-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  margin-top: 40px;
}

.msg-group { display: flex; flex-direction: column; gap: 6px; }

.bubble-row { display: flex; }
.user-row { justify-content: flex-end; }
.ai-row   { justify-content: flex-start; }

.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
}

.bubble-user {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble-ai {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-text { white-space: pre-wrap; }

/* Badges */
.ticker-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.2);
  color: var(--accent);
  align-self: flex-start;
}
.context-badge {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  align-self: flex-start;
}
.ctx-portfolio { background: rgba(34,197,94,0.15); color: #22c55e; }
.ctx-ticker    { background: rgba(59,130,246,0.15); color: #3b82f6; }
.ctx-general   { background: rgba(148,163,184,0.1); color: var(--text-muted); }

/* Typing dots */
.typing {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: bounce 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-5px); }
}

/* Error */
.chat-error {
  flex-shrink: 0;
  font-size: 12px;
  color: #ef4444;
  padding: 6px 10px;
  background: rgba(239,68,68,0.08);
  border-radius: 6px;
  border: 1px solid rgba(239,68,68,0.2);
}

/* Input bar */
.input-bar {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding-bottom: 8px;
}

.chat-input {
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: 10px 14px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}
.chat-input:focus { border-color: var(--accent); }
.chat-input:disabled { opacity: 0.5; }
.chat-input::placeholder { color: var(--text-muted); }

.send-btn {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn:hover:not(:disabled) { opacity: 0.85; }

@media (max-width: 640px) {
  .chat-page { height: calc(100vh - 76px); }
  .bubble { max-width: 92%; }
  .quick-actions { gap: 6px; }
  .quick-chip { font-size: 11px; padding: 4px 10px; }
}
</style>
