<script setup lang="ts">
import { onMounted, onUnmounted, nextTick, ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import AccessibleButton from '../../components/AccessibleButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import AppIcon from '../../components/AppIcon.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import MobileShell from '../../components/MobileShell.vue';
import TaskDraftCard from '../../components/TaskDraftCard.vue';
import { labelTextControl } from '../../platform/accessibility';
import { bindComposer } from '../../platform/composer';
import { requestId } from '../../platform/ids';
import { openWebSource } from '../../platform/navigation';
import { currentUser, restoreSession, sessionError } from '../../stores/session';
import { draft } from '../../stores/ui';
import { activeConversation, messages, busy, loading, chatError, olderCursor, loadChat, loadOlder, sendText, retryReply, modelMode, modelConfigured, type Message, type MemoryReference } from '../../stores/chat';
import { updateTaskDraft } from '../../stores/chat';
const scrollTarget = ref('');
const expandedSearch = ref<Record<string, boolean>>({});
const composerId = `chat-draft-${requestId()}`;
let freshRequested = false;
const focusInput = ref(false);
const composing = ref(false);
let removeKeyboard = () => {};
const suggestions = ['想聊聊今天发生的事', '有件事想请你帮忙记住', '我想安排一次出行'];
function updateDraft(event: Event) {
  // #ifndef H5
  draft.value = (event as unknown as { detail: { value: string } }).detail.value;
  // #endif
  // H5 uses synchronous native input in the platform adapter.
  void event;
}
async function chooseSuggestion(text: string) { draft.value = text; focusInput.value = false; await nextTick(); focusInput.value = true; }
async function newest() { scrollTarget.value = ''; await nextTick(); scrollTarget.value = 'chat-tail'; }
async function send() {
  if (loading.value || composing.value) return;
  const saved = await sendText();
  if (saved && freshRequested && activeConversation.value) {
    freshRequested = false;
    uni.redirectTo({ url: `/pages/index/index?id=${activeConversation.value.id}` });
  } else await newest();
}
async function retry(item: Message) { await retryReply(item); await newest(); }
function openEvidence(reference: MemoryReference) { uni.navigateTo({ url: `/pages/index/index?id=${reference.conversation_id}` }); }
onMounted(async () => { await nextTick(); labelTextControl(composerId, '想对小忆说的话'); removeKeyboard = bindComposer(composerId, send, newest, value => { draft.value = value; }); });
onUnmounted(() => removeKeyboard());
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
      <AppHeader
        companion
        :thinking="busy"
      />
    </template>
    <view class="mode-note">
      {{ modelMode === 'mock' ? 'Mock 测试模式 · 消息真实保存' : modelMode === 'deepseek' ? (modelConfigured ? 'DeepSeek · 消息真实保存' : 'DeepSeek 尚未配置 · 消息仍可保存') : '正在检查模型服务…' }}
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
          v-else-if="!messages.length && !busy"
          class="empty-chat"
        >
          <text class="empty-title">
            今天想聊些什么？
          </text><text>小事也可以，慢慢说。</text>
          <view class="suggestions">
            <AccessibleButton
              v-for="text in suggestions"
              :key="text"
              class="suggestion"
              :disabled="loading"
              @click="chooseSuggestion(text)"
            >
              {{ text }}
            </AccessibleButton>
          </view>
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
            <text>{{ message.error_code === 'MODEL_NOT_CONFIGURED' ? '消息已保存，需管理员配置模型服务。' : message.error_code === 'MODEL_BUDGET_EXCEEDED' ? '消息已保存，今日模型预算不足，未调用模型。' : '消息已保存，模型回复失败或结果不明。为避免重复计费，不会自动重试。' }}</text>
            <AccessibleButton
              v-if="['MODEL_NOT_CONFIGURED', 'MODEL_BUDGET_EXCEEDED'].includes(message.error_code || '')"
              class="retry-button"
              :loading="busy"
              @click="retry(message)"
            >
              重试回复
            </AccessibleButton>
          </view>
          <view
            v-if="message.role === 'assistant' && message.status === 'pending'"
            class="reply-error"
            role="status"
          >
            回复仍在处理中，或服务曾中断；可重新读取历史查看状态，不会重复调用模型。
          </view>
          <text class="message-time">
            {{ message.status === 'sending' ? '发送中，尚未确认保存' : new Date(message.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
          </text>
          <view
            v-if="message.search_context?.status === 'completed'"
            class="memory-reference"
          >
            <text>联网天气参考 · {{ message.search_context.city }} · {{ message.search_context.date }}</text>
            <AccessibleButton
              secondary
              :aria-expanded="!!expandedSearch[message.id]"
              @click="expandedSearch[message.id] = !expandedSearch[message.id]"
            >
              {{ expandedSearch[message.id] ? '收起天气来源' : '查看天气来源' }}
            </AccessibleButton>
            <view v-if="expandedSearch[message.id]">
              <text v-if="message.search_context.queried_at">
                查询时间：{{ message.search_context.queried_at }}
              </text>
              <AccessibleButton
                v-for="source in message.search_context.results || []"
                :key="source.url"
                secondary
                @click="openWebSource(source.url)"
              >
                {{ source.title }}
              </AccessibleButton>
            </view>
          </view>
          <TaskDraftCard
            v-for="task in message.task_drafts || []"
            :key="task.id"
            :item="task"
            @changed="updateTaskDraft"
          />
          <view
            v-for="reference in message.memory_refs || []"
            :key="reference.label"
            class="memory-reference"
          >
            <text class="reference-title">
              记忆依据 · {{ ['inactive', 'invalid', 'superseded', 'historical'].includes(reference.status) ? '历史记录，已失效' : reference.confirmed ? '已确认' : '候选，待确认' }}{{ reference.extractor_provider === 'mock' ? ' · Mock' : '' }}{{ reference.is_synthetic ? ' · Synthetic' : '' }}
            </text>
            <text
              v-if="reference.changed_since_reply"
              class="reference-title"
            >
              此回复使用的是旧版本，记忆已更新；请到“我的回忆”核对。
            </text>
            <text>{{ reference.evidence_origin === 'user_edit' ? '用户修改后的依据：' : '' }}{{ reference.evidence_text || reference.source_excerpt }}</text>
            <text
              v-if="reference.evidence_origin === 'user_edit'"
              class="reference-title"
            >
              原始聊天：{{ reference.source_excerpt }}（保留溯源，不作为纠错后的事实）
            </text>
            <AccessibleButton
              class="retry-button"
              @click="openEvidence(reference)"
            >
              打开原会话
            </AccessibleButton>
          </view>
          <text
            v-if="message.role === 'user' && message.memory_status && message.memory_status !== 'disabled'"
            class="message-time"
          >
            {{ message.memory_status === 'captured' ? '已检查候选记忆，可在“我的回忆”核对' : message.memory_status === 'partial_rejected' ? '缺少原文依据的候选已忽略' : '本条记忆提取未完成' }}
          </text>
        </view>
        <view
          v-if="busy"
          class="quiet-state"
          role="status"
        >
          正在保存消息并生成回复…
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
          :for="composerId"
        >想对小忆说的话</label>
        <textarea
          :id="composerId"
          :value="draft"
          class="draft-input"
          placeholder="说点什么吧…"
          placeholder-style="color:#586761;opacity:1"
          :maxlength="2000"
          auto-height
          :focus="focusInput"
          :ignore-composition-event="false"
          :show-confirm-bar="false"
          :cursor-spacing="20"
          confirm-type="send"
          @focus="newest"
          @input="updateDraft"
          @keyboardheightchange="newest"
          @compositionstart="composing = true"
          @compositionend="composing = false"
          @blur="composing = false"
          @confirm="send"
        />
        <AccessibleButton
          v-if="draft.trim() || busy"
          class="send-button"
          :loading="busy"
          :disabled="loading || composing"
          :error="!!chatError"
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
.suggestions { display: flex; flex-direction: column; gap: 10px; margin-top: 28px; }
.suggestion { min-height: 48px; padding: 10px 16px; border: 1px solid var(--color-line); border-radius: 18px; color: var(--color-primary-dark); background: var(--color-surface); font-size: 16px; line-height: 1.6; }
.quiet-state { text-align: center; color: var(--color-muted); padding: 24px; }
.message-row { display: flex; flex-direction: column; margin-bottom: 22px; }
.message-row.user { align-items: flex-end; }
.message { max-width: 92%; padding: 14px 18px; line-height: 1.75; overflow-wrap: anywhere; white-space: pre-wrap; background: var(--color-surface); border-radius: 6px 22px 22px 22px; }
.user .message { background: var(--color-bubble); border-radius: 22px 22px 6px 22px; }
.speaker { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; font-size: 14px; color: var(--color-muted); }
.speaker-avatar { width: 25px; height: 25px; }
.message-time { color: var(--color-muted); font-size: 15px; line-height: 1.6; margin-top: 5px; }
.reply-error { background: var(--color-soft); padding: 14px; border-radius: 16px; line-height: 1.7; color: var(--color-muted); font-size: 16px; }
.retry-button { min-height: 44px; color: var(--color-primary-dark); padding: 8px; font-size: 16px; }
.older-button { min-height: 48px; color: var(--color-primary-dark); font-size: 16px; }
.composer-area { flex-shrink: 0; padding: 4px 20px 16px; }
.composer { display: flex; align-items: center; gap: 8px; min-height: 60px; padding: 6px 8px 6px 18px; background: white; border: 1px solid var(--color-line); border-radius: 32px; }
.draft-input { flex: 1; width: 0; min-width: 0; min-height: 28px; max-height: 112px; font-size: var(--font-body); line-height: 28px; color: var(--color-text); }
.draft-input :deep(.uni-textarea-wrapper) { max-height: 112px; }
.draft-input :deep(textarea) { max-height: 112px; overflow-y: auto !important; }
.send-button { min-width: 64px; min-height: 44px; padding: 8px 12px; border-radius: 24px; background: var(--color-primary); color: white; font-size: 16px; flex-shrink: 0; }
.send-button[aria-disabled="false"]:hover { background: var(--color-primary-dark); }
.voice-button { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; flex-shrink: 0; }
.inline-error { color: var(--color-error); font-size: 16px; line-height: 1.6; padding: 8px 4px; }
.tail { height: 1px; }
.memory-reference { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px; margin-top: 10px; max-width: 92%; border: 1px solid var(--color-line); border-radius: 16px; line-height: 1.7; font-size: 16px; overflow-wrap: anywhere; }
.reference-title { font-size: 14px; color: var(--color-muted); }
</style>
