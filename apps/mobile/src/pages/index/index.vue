<script setup lang="ts">
import { onMounted, nextTick, ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import AccessibleButton from '../../components/AccessibleButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import AppIcon from '../../components/AppIcon.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import MobileShell from '../../components/MobileShell.vue';
import { labelTextControl } from '../../platform/accessibility';
import { currentUser, restoreSession, sessionError } from '../../stores/session';
import { draft } from '../../stores/ui';
import { activeConversation, messages, busy, loading, chatError, olderCursor, loadChat, loadOlder, sendText, retryReply, type Message } from '../../stores/chat';
const scrollTarget = ref('');
let freshRequested = false;
async function newest() { scrollTarget.value = ''; await nextTick(); scrollTarget.value = 'chat-tail'; }
async function send() {
  if (loading.value) return;
  const saved = await sendText();
  if (saved && freshRequested && activeConversation.value) {
    freshRequested = false;
    uni.redirectTo({ url: `/pages/index/index?id=${activeConversation.value.id}` });
  } else await newest();
}
async function retry(item: Message) { await retryReply(item); await newest(); }
onMounted(() => labelTextControl('chat-draft', '想对小忆说的话'));
onLoad(async options => {
  freshRequested = options?.new === '1';
  if (!currentUser.value) await restoreSession();
  if (!currentUser.value) {
    if (sessionError.value) chatError.value = sessionError.value;
    else uni.reLaunch({ url: '/pages/login/index' });
    return;
  }
  await loadChat(options?.id, options?.new === '1');
  await newest();
});
</script>
<template>
  <MobileShell>
    <template #header>
      <AppHeader companion />
    </template>
    <view class="mode-note">
      消息真实保存 · 模型回复尚未接入
    </view>
    <scroll-view
      class="chat-scroll"
      scroll-y
      :scroll-into-view="scrollTarget"
      :aria-busy="loading"
    >
      <view class="conversation">
        <AccessibleButton
          v-if="olderCursor"
          class="older-button"
          :loading="loading"
          @click="loadOlder"
        >
          查看更早的消息
        </AccessibleButton>
        <text
          v-if="loading && !messages.length"
          class="quiet-state"
          role="status"
        >
          正在读取聊天…
        </text>
        <view
          v-else-if="!messages.length"
          class="empty-chat"
        >
          <text class="empty-title">
            今天想聊些什么？
          </text><text>小事也可以，慢慢说。</text>
        </view>
        <view
          v-for="message in messages"
          :id="`message-${message.id}`"
          :key="message.id"
          class="message-row"
          :class="message.role"
        >
          <view
            v-if="message.role === 'assistant'"
            class="speaker"
          >
            <image
              src="/static/companion.svg"
              class="speaker-avatar"
            /><text>小忆</text>
          </view>
          <view
            v-if="message.content"
            class="message"
          >
            <text selectable>
              {{ message.content }}
            </text>
          </view>
          <view
            v-if="message.role === 'assistant' && message.status === 'failed'"
            class="reply-error"
            role="status"
          >
            <text>{{ message.error_code === 'MODEL_NOT_CONFIGURED' ? '你的消息已保存，模型回复尚未接入。' : '回复失败，你的消息已保留。' }}</text><AccessibleButton
              class="retry-button"
              :loading="busy"
              @click="retry(message)"
            >
              重试回复
            </AccessibleButton>
          </view>
          <text class="message-time">
            {{ new Date(message.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
          </text>
        </view>
        <view
          id="chat-tail"
          class="tail"
        />
      </view>
    </scroll-view>
    <view class="composer-area">
      <view
        v-if="chatError"
        class="inline-error"
        role="alert"
      >
        <text>{{ chatError }}</text><AccessibleButton
          class="retry-button"
          :disabled="busy"
          @click="send"
        >
          重试发送
        </AccessibleButton>
      </view>
      <view class="composer">
        <label
          class="sr-only"
          for="chat-draft"
        >想对小忆说的话</label>
        <input
          id="chat-draft"
          v-model="draft"
          class="draft-input"
          placeholder="说点什么吧…"
          :maxlength="2000"
          confirm-type="send"
          @confirm="send"
        >
        <AccessibleButton
          v-if="draft.trim() || busy"
          class="send-button"
          :loading="busy"
          :disabled="loading"
          aria-label="发送消息"
          @click="send"
        >
          {{ busy ? '发送中' : '发送' }}
        </AccessibleButton>
        <AccessibleButton
          v-else
          class="voice-button"
          disabled
          aria-label="语音输入，暂未开放"
        >
          <AppIcon
            name="mic"
            :size="25"
          />
        </AccessibleButton>
      </view>
    </view>
    <template #footer>
      <BottomTabs active="chat" />
    </template>
  </MobileShell>
</template>
<style scoped>
.mode-note { padding: 6px 18px; color: var(--color-muted); font-size: 14px; text-align: center; }
.chat-scroll { flex: 1; height: 0; min-height: 0; }
.conversation { min-height: 100%; display: flex; flex-direction: column; padding: 20px 22px 8px; }
.empty-chat { margin: auto 0; padding: 44px 0; text-align: center; line-height: 1.8; color: var(--color-muted); }
.empty-chat text { display: block; }
.empty-title { font-size: 24px; color: var(--color-text); margin-bottom: 12px; }
.quiet-state { text-align: center; color: var(--color-muted); padding: 24px; }
.message-row { display: flex; flex-direction: column; margin-bottom: 22px; }
.message-row.user { align-items: flex-end; }
.message { max-width: 92%; padding: 14px 18px; line-height: 1.75; overflow-wrap: anywhere; white-space: pre-wrap; background: var(--color-surface); border-radius: 6px 22px 22px 22px; }
.user .message { background: var(--color-bubble); border-radius: 22px 22px 6px 22px; }
.speaker { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; font-size: 14px; color: var(--color-muted); }
.speaker-avatar { width: 25px; height: 25px; }
.message-time { color: var(--color-muted); font-size: 14px; line-height: 1.6; margin-top: 5px; }
.reply-error { background: var(--color-soft); padding: 14px; border-radius: 16px; line-height: 1.7; color: var(--color-muted); font-size: 16px; }
.retry-button { min-height: 44px; color: var(--color-primary-dark); padding: 8px; font-size: 16px; }
.older-button { min-height: 48px; color: var(--color-primary-dark); font-size: 16px; }
.composer-area { flex-shrink: 0; padding: 4px 20px 16px; }
.composer { display: flex; align-items: center; gap: 8px; min-height: 60px; padding: 6px 8px 6px 18px; background: white; border: 1px solid var(--color-line); border-radius: 32px; }
.draft-input { flex: 1; width: 0; min-width: 0; height: 44px; font-size: var(--font-body); color: var(--color-text); }
.send-button { min-width: 64px; min-height: 44px; padding: 8px 12px; border-radius: 24px; background: var(--color-primary); color: white; font-size: 16px; flex-shrink: 0; }
.voice-button { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; flex-shrink: 0; }
.inline-error { color: var(--color-error); font-size: 16px; line-height: 1.6; padding: 8px 4px; }
.tail { height: 1px; }
</style>
