<script setup lang="ts">
import AccessibleButton from '../../components/AccessibleButton.vue';
import { onMounted, ref } from 'vue';
import AppHeader from '../../components/AppHeader.vue';
import AppIcon from '../../components/AppIcon.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import MobileShell from '../../components/MobileShell.vue';
import { draft } from '../../stores/ui';
import { labelTextControl } from '../../platform/accessibility';

onMounted(() => labelTextControl('chat-draft', '想对小忆说的话'));

const feedback = ref('');
function previewSend() {
  feedback.value = '当前是界面预览，消息尚未发送。对话功能接入后即可使用。';
}
function notAvailable() {
  uni.showToast({ title: '语音、图片将在后续版本开放', icon: 'none' });
}
function showSource() {
  uni.showModal({
    title: '记忆来源 · 样式预览',
    content: '这是一段合成示例对话，展示未来的来源入口。当前没有提取或保存任何记忆。',
    showCancel: false,
    confirmText: '知道了',
    confirmColor: '#347f70',
  });
}
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader companion />
    </template>
    <view class="gentle-prompt">
      <text>今天想聊些什么？随时都可以告诉我。</text>
    </view>
    <scroll-view
      class="chat-scroll"
      scroll-y
    >
      <view class="conversation">
        <view class="conversation-label">
          <text>今天</text><text class="preview-label">
            界面预览 · 示例对话
          </text>
        </view>
        <view class="user-row">
          <view class="message user-message">
            <text selectable>
              今天和王姐出去散步了，路上还遇到了老同学。
            </text>
          </view>
        </view>
        <view class="assistant-row">
          <view class="speaker">
            <image
              src="/static/companion.svg"
              class="speaker-avatar"
            /><text>小忆</text>
          </view>
          <view class="message assistant-message">
            <text selectable>
              听起来今天过得很充实呀。和老朋友见面，总有说不完的话吧？
            </text>
          </view>
          <AccessibleButton
            class="source-link"
            @click="showSource"
          >
            <AppIcon
              name="bookmark-check"
              :size="16"
            /><text>记忆来源样式预览</text><AppIcon
              name="chevron-right"
              :size="14"
            />
          </AccessibleButton>
        </view>
      </view>
    </scroll-view>
    <view class="composer-area">
      <view
        v-if="feedback"
        class="inline-feedback"
        role="status"
        aria-live="polite"
      >
        <text>{{ feedback }}</text>
      </view>
      <view class="composer">
        <AccessibleButton
          class="add-button"
          aria-label="更多输入方式，暂未开放"
          @click="notAvailable"
        >
          <AppIcon
            name="plus"
            :size="23"
          />
        </AccessibleButton>
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
          @confirm="previewSend"
        >
        <AccessibleButton
          v-if="draft.trim()"
          class="send-button"
          aria-label="发送消息"
          @click="previewSend"
        >
          <AppIcon
            name="arrow-up-white"
            :size="25"
          />
        </AccessibleButton>
        <AccessibleButton
          v-else
          class="voice-button"
          aria-label="语音输入，暂未开放"
          @click="notAvailable"
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
.gentle-prompt { flex-shrink: 0; margin: 4px 22px 0; padding: 9px 14px; text-align: center; border-radius: 22px; background: var(--color-soft); color: #42665b; font-size: 14px; line-height: 1.5; }
.chat-scroll { flex: 1; height: 0; min-height: 0; }
.conversation { min-height: 100%; display: flex; flex-direction: column; justify-content: flex-end; padding: 28px 22px 8px; }
.conversation-label { display: flex; align-items: center; justify-content: center; gap: 12px; color: var(--color-muted); font-size: 13px; margin-bottom: 34px; }
.user-row { display: flex; justify-content: flex-end; margin-bottom: 22px; }
.message { max-width: 88%; padding: 16px 18px; line-height: 1.75; overflow-wrap: anywhere; }
.user-message { border-radius: 22px 22px 6px 22px; background: var(--color-bubble); }
.speaker { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; font-size: 14px; color: var(--color-muted); }
.speaker-avatar { width: 25px; height: 25px; }
.assistant-message { max-width: 96%; border-radius: 6px 22px 22px 22px; background: var(--color-surface); }
.source-link { display: flex; align-items: center; gap: 5px; min-height: 44px; padding: 6px 0; font-size: 13px; color: var(--color-primary-dark); }
.source-link:active { opacity: .65; }
.composer-area { flex-shrink: 0; padding: 4px 20px 16px; }
.composer { display: flex; align-items: center; gap: 4px; min-height: 60px; padding: 6px; background: white; border: 1px solid #cfdcd3; border-radius: 32px; }
.draft-input { flex: 1; width: 0; min-width: 0; height: 44px; padding: 0 4px; font-size: var(--font-body); color: var(--color-text); }
.add-button { display: flex; justify-content: center; align-items: center; width: 44px; height: 44px; border-radius: 50%; flex-shrink: 0; }
.send-button, .voice-button { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; flex-shrink: 0; }
.send-button { background: var(--color-primary); }
.send-button:active, .send-button:hover { background: var(--color-primary-dark); }
.voice-button { background: transparent; }
.inline-feedback { color: var(--color-primary-dark); font-size: 14px; line-height: 1.6; padding: 8px 4px; }
@media (max-height: 700px) { .conversation { padding-top: 16px; } .conversation-label { margin-bottom: 18px; } .user-row { margin-bottom: 14px; } }
</style>
