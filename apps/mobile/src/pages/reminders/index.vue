<script setup lang="ts">
import AppHeader from '../../components/AppHeader.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader title="提醒" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content">
        <text class="page-title">
          小事，也值得记挂。
        </text><text class="page-description">
          给生活留一点从容。
        </text><text class="preview-label">
          界面预览 · 提醒功能尚未接入
        </text>
      </view>
      <EmptyState
        icon="bell"
        title="还没有待办的事"
        description="以后可以从聊天中确认赴约安排，结合路程和天气安排出门，并开启浏览器提醒。当前尚未接入。"
      />
    </scroll-view>
    <template #footer>
      <BottomTabs active="reminders" />
    </template>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
</style>
