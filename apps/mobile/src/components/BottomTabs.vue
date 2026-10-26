<script setup lang="ts">
import AccessibleButton from './AccessibleButton.vue';
import AppIcon from './AppIcon.vue';

defineProps<{ active?: string }>();
const tabs = [
  { id: 'chat', label: '聊天', icon: 'message-circle', path: '/pages/index/index' },
  { id: 'timeline', label: '我的回忆', icon: 'notebook-pen', path: '/pages/timeline/index' },
  { id: 'reminders', label: '提醒', icon: 'bell', path: '/pages/reminders/index' },
];
function open(path: string) {
  uni.redirectTo({ url: path });
}
</script>

<template>
  <view
    class="bottom-tabs"
    role="navigation"
    aria-label="主导航"
  >
    <AccessibleButton
      v-for="tab in tabs"
      :key="tab.id"
      class="tab"
      :class="{ selected: active === tab.id }"
      :aria-current="active === tab.id ? 'page' : undefined"
      @click="active !== tab.id && open(tab.path)"
    >
      <view class="tab-icon">
        <AppIcon
          :name="tab.icon"
          :active="active === tab.id"
          :size="23"
        />
      </view>
      <text>{{ tab.label }}</text>
    </AccessibleButton>
  </view>
</template>

<style scoped>
.bottom-tabs { display: flex; flex-shrink: 0; margin: 0 20px; padding: 8px 0 calc(9px + env(safe-area-inset-bottom)); border-top: 1px solid var(--color-line); }
.tab { flex: 1; min-width: 0; min-height: 62px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; color: var(--color-muted); font-size: 15px; border-radius: 16px; transition: background var(--motion-duration); }
.tab-icon { padding: 3px 15px; border-radius: 18px; }
.tab.selected { color: var(--color-primary-dark); font-weight: 600; }
.selected .tab-icon { background: var(--color-soft); }
.tab:active, .tab:hover { background: var(--color-soft); }
</style>
