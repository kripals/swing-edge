<template>
  <span class="info-wrap" @mouseenter="open = true" @mouseleave="open = false" @click.stop="open = !open">
    <span class="info-icon">?</span>
    <div v-if="open" class="info-tooltip" :class="position">
      {{ text }}
    </div>
  </span>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  text: { type: String, required: true },
  position: { type: String, default: 'top' }, // 'top' | 'bottom' | 'left'
})

const open = ref(false)
</script>

<style scoped>
.info-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  margin-left: 4px;
  vertical-align: middle;
  cursor: pointer;
  flex-shrink: 0;
}

.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--border);
  color: var(--text-muted);
  font-size: 9px;
  font-weight: 700;
  font-style: normal;
  line-height: 1;
  flex-shrink: 0;
  transition: background 0.15s;
}

.info-wrap:hover .info-icon {
  background: var(--accent);
  color: #fff;
}

.info-tooltip {
  position: absolute;
  z-index: 100;
  background: #1e293b;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text);
  line-height: 1.5;
  width: 220px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  pointer-events: none;
}

/* Positions */
.info-tooltip.top {
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
}

.info-tooltip.bottom {
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
}

.info-tooltip.left {
  bottom: calc(100% + 6px);
  right: 0;
  left: auto;
  transform: none;
}
</style>
