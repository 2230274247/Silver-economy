<script setup lang="ts">
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
function openChat() { uni.redirectTo({ url: '/pages/index/index' }); }
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader title="我的回忆" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content">
        <text class="page-title">
          值得记住的，都在这里。
        </text><text class="page-description">
          你的故事，会按时间慢慢展开。
        </text><text class="preview-label">
          界面预览 · 尚未接入记忆数据
        </text>
      </view>
      <EmptyState
        icon="notebook-pen"
        title="故事，从一段聊天开始"
        description="以后，你确认保存的生活片段会出现在这里，也能查看它来自哪次聊天。"
      >
        <AppButton
          secondary
          @click="openChat"
        >
          去聊聊天
        </AppButton>
      </EmptyState>
    </scroll-view>
    <template #footer>
      <BottomTabs active="timeline" />
    </template>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
</style>
