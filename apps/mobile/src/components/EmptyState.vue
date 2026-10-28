<script setup lang="ts">
import AppIcon from './AppIcon.vue';
defineProps<{ icon: string; title: string; description: string }>();
</script>

<template>
  <view class="empty-state">
    <view class="empty-icon">
      <AppIcon
        :name="icon"
        :size="32"
      />
    </view>
    <text class="empty-title">
      {{ title }}
    </text>
    <text class="empty-description">
      {{ description }}
    </text>
    <view class="empty-action">
      <slot />
    </view>
  </view>
</template>

<style scoped>
.empty-state { padding: 48px 24px; text-align: center; }
.empty-icon { width: 76px; height: 76px; display: flex; align-items: center; justify-content: center; border-radius: 26px; margin: 0 auto 24px; background: var(--color-soft); }
.empty-title { display: block; font-size: 23px; font-weight: 600; line-height: 1.5; }
.empty-description { display: block; color: var(--color-muted); margin-top: 12px; line-height: 1.8; }
.empty-action { margin-top: 28px; }
</style>
