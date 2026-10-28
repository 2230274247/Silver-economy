<script setup lang="ts">
import { ref } from 'vue';
import { onShow } from '@dcloudio/uni-app';
import AccessibleButton from '../../components/AccessibleButton.vue';
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
import { conversations, conversationCursor, historyError, loadConversations } from '../../stores/chat';
const reading = ref(false);
async function reload(more = false) { if (reading.value) return; reading.value = true; try { await loadConversations(more); } finally { reading.value = false; } }
function open(id: string) { uni.redirectTo({ url: `/pages/index/index?id=${id}` }); }
function fresh() { uni.redirectTo({ url: '/pages/index/index?new=1' }); }
onShow(() => { void reload(); });
</script>
<template>
  <MobileShell>
    <template #header>
      <AppHeader title="聊天记录" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="history-content">
        <AppButton @click="fresh">
          开始新对话
        </AppButton>
        <text
          v-if="historyError"
          role="alert"
          class="error"
        >
          {{ historyError }}
        </text><AppButton
          v-if="historyError"
          secondary
          :loading="reading"
          @click="reload()"
        >
          重新读取
        </AppButton>
        <text
          v-if="reading && !conversations.length"
          class="notice"
          role="status"
        >
          正在读取会话…
        </text>
        <EmptyState
          v-else-if="!conversations.length && !historyError"
          icon="message-circle"
          title="每次聊天，都可以接着说"
          description="还没有聊天记录，开始一段新对话吧。"
        />
        <AccessibleButton
          v-for="item in conversations"
          :key="item.id"
          class="history-item"
          @click="open(item.id)"
        >
          <text class="history-title">
            {{ item.title }}
          </text><text class="history-date">
            {{ new Date(item.created_at).toLocaleDateString('zh-CN') }}
          </text>
        </AccessibleButton>
        <AppButton
          v-if="conversationCursor"
          secondary
          :loading="reading"
          @click="reload(true)"
        >
          更早的会话
        </AppButton>
      </view>
    </scroll-view>
  </MobileShell>
</template>
<style scoped>
.content-scroll { height: 0; flex: 1; }
.history-content { display: flex; flex-direction: column; gap: 16px; padding: 20px 22px; }
.history-item { text-align: left; padding: 18px; min-height: 76px; border-radius: 18px; background: var(--color-surface); }
.history-title { display: block; font-size: var(--font-body); line-height: 1.6; overflow-wrap: anywhere; }
.history-date { display: block; font-size: 14px; color: var(--color-muted); margin-top: 6px; }
.error { color: var(--color-error); line-height: 1.7; }
.notice { color: var(--color-muted); text-align: center; padding: 16px; }
</style>
