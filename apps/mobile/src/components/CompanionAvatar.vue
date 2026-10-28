<script setup lang="ts">
withDefaults(defineProps<{ state?: 'waiting' | 'listening' | 'thinking' | 'responding'; size?: number }>(), {
  state: 'waiting',
  size: 58,
});
const labels = {
  waiting: '等待交流',
  listening: '正在倾听',
  thinking: '正在思考',
  responding: '温柔回应',
};
</script>

<template>
  <view
    class="companion-avatar"
    :class="state"
    :style="{ width: `${size}px`, height: `${size}px` }"
    role="img"
    :aria-label="`小忆，${labels[state]}`"
  >
    <image
      class="companion-image"
      src="/static/companion.svg"
      mode="aspectFit"
      aria-hidden="true"
    />
    <view
      class="status-dot"
      aria-hidden="true"
    />
  </view>
</template>

<style scoped>
.companion-avatar { position: relative; flex-shrink: 0; }
.companion-image { width: 100%; height: 100%; transform-origin: center bottom; }
.waiting .companion-image { animation: quiet-breath 5s ease-in-out infinite; }
.status-dot { position: absolute; right: 2px; bottom: 3px; width: 9px; height: 9px; border: 2px solid var(--color-bg); border-radius: 50%; background: var(--color-primary); }
.listening .status-dot { background: #347f70; animation: listen-pulse 2s ease-in-out infinite; }
.thinking .status-dot { background: #61869b; }
.responding .status-dot { background: #b27a75; }
.responding .companion-image { animation: gentle-nod 700ms ease-in-out 1; }
@keyframes quiet-breath { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.025); } }
@keyframes listen-pulse { 50% { transform: scale(1.15); } }
@keyframes gentle-nod { 50% { transform: translateY(2px); } }
@media (prefers-reduced-motion: reduce) { .companion-image, .status-dot { animation: none !important; } }
</style>
