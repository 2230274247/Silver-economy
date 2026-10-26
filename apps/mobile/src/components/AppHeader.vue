<script setup lang="ts">
import AccessibleButton from './AccessibleButton.vue';
import AppIcon from './AppIcon.vue';
import CompanionAvatar from './CompanionAvatar.vue';

withDefaults(defineProps<{ title?: string; companion?: boolean; showSettings?: boolean }>(), {
  title: '',
  companion: false,
  showSettings: true,
});

function openHistory() {
  uni.navigateTo({ url: '/pages/history/index' });
}
function openSettings() {
  uni.navigateTo({ url: '/pages/me/index' });
}
function goBack() {
  if (getCurrentPages().length > 1) uni.navigateBack();
  else uni.redirectTo({ url: '/pages/index/index' });
}
</script>

<template>
  <view
    class="app-header"
    :class="{ companion }"
  >
    <AccessibleButton
      v-if="companion"
      class="icon-button"
      aria-label="查看聊天记录"
      @click="openHistory"
    >
      <AppIcon name="menu" />
    </AccessibleButton>
    <AccessibleButton
      v-else
      class="icon-button"
      aria-label="返回聊天"
      @click="goBack"
    >
      <AppIcon name="chevron-left" />
    </AccessibleButton>
    <view
      v-if="companion"
      class="identity"
    >
      <CompanionAvatar />
      <text class="companion-name">
        小忆 <text class="identity-caption">
          AI 伙伴
        </text>
      </text>
    </view>
    <text
      v-else
      class="header-title"
    >
      {{ title }}
    </text>
    <AccessibleButton
      v-if="showSettings"
      class="icon-button"
      aria-label="打开个人设置"
      @click="openSettings"
    >
      <AppIcon name="sliders-horizontal" />
    </AccessibleButton>
    <view
      v-else
      class="header-spacer"
      aria-hidden="true"
    />
  </view>
</template>

<style scoped>
.app-header { display: flex; align-items: center; justify-content: space-between; min-height: 76px; padding: 8px 16px; gap: 8px; flex-shrink: 0; }
.app-header.companion { min-height: 108px; padding-top: 12px; }
.identity { display: flex; align-items: center; flex-direction: column; gap: 5px; }
.header-spacer { width: 48px; }
.companion-name { font-size: 16px; font-weight: 600; }
.identity-caption { font-size: 13px; font-weight: 400; color: var(--color-muted); margin-left: 4px; }
.header-title { font-size: 20px; font-weight: 600; }
</style>
