<script setup lang="ts">
import AccessibleButton from '../../components/AccessibleButton.vue';
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import MobileShell from '../../components/MobileShell.vue';
import { fontSize, setFontSize } from '../../stores/ui';
import type { FontSize } from '../../platform/storage';
import { ref } from 'vue';
import { currentUser, logout, sessionError } from '../../stores/session';
import { onShow } from '@dcloudio/uni-app';
import { request } from '../../platform/network';
const busy = ref(false);
const accountError = ref('');
const memoryEnabled = ref(false);
const memoryBusy = ref(false);
const memoryLoading = ref(true);
const memoryReady = ref(false);
const memoryError = ref('');
async function readMemoryConsent() {
  memoryLoading.value = true;
  memoryReady.value = false; memoryError.value = '';
  try { if (currentUser.value) { memoryEnabled.value = (await request<{ enabled: boolean }>('/memory-consent')).enabled; memoryReady.value = true; } }
  catch { memoryError.value = '记忆设置读取失败，请重试。'; }
  finally { memoryLoading.value = false; }
}
onShow(readMemoryConsent);
async function toggleMemory() {
  if (memoryBusy.value || memoryLoading.value || !memoryReady.value) return;
  memoryBusy.value = true; memoryError.value = '';
  try {
    if (!memoryEnabled.value) {
      const choice = await uni.showModal({ title: '开启长期记忆', content: '允许从聊天提取有原文依据的候选记忆，并在后续会话检索使用。候选未经本人确认，回复会提供来源供核对。可以随时关闭；关闭不会删除聊天或已有记忆。', confirmText: '允许', cancelText: '暂不' });
      if (!choice.confirm) return;
    }
    memoryEnabled.value = (await request<{ enabled: boolean }>('/memory-consent', 'POST', { enabled: !memoryEnabled.value })).enabled;
  } catch { memoryError.value = '记忆设置保存失败，请重试。'; }
  finally { memoryBusy.value = false; }
}
const sizes: { size: FontSize; label: string }[] = [{ size: 18, label: '标准' }, { size: 20, label: '大号' }, { size: 22, label: '特大' }];
function openLogin() { uni.navigateTo({ url: '/pages/login/index' }); }
async function leave() {
  if (busy.value) return;
  busy.value = true; accountError.value = '';
  try { await logout(); uni.reLaunch({ url: '/pages/login/index' }); }
  catch { accountError.value = '退出失败，请检查网络后重试。当前会话尚未注销。'; }
  finally { busy.value = false; }
}
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader
        title="个人设置"
        :show-settings="false"
      />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content settings-content">
        <view class="profile">
          <image
            src="/static/companion.svg"
            class="profile-avatar"
          /><view>
            <text class="profile-title">
              时光有声
            </text><text class="page-description">
              按你舒服的方式，慢慢聊。
            </text>
            <text
              v-if="currentUser"
              class="setting-note"
            >
              已登录：{{ currentUser.login_name }}
            </text>
          </view>
        </view>
        <view class="surface-card">
          <text class="setting-title">
            阅读字号
          </text><text class="setting-note">
            所有页面一起调整，自动记住你的选择。
          </text><view class="font-options">
            <AccessibleButton
              v-for="item in sizes"
              :key="item.size"
              :class="{ chosen: fontSize === item.size }"
              :aria-pressed="fontSize === item.size"
              @click="setFontSize(item.size)"
            >
              {{ item.label }}
            </AccessibleButton>
          </view><text class="font-sample">
            今天也有值得记住的小事。
          </text>
        </view>
        <view class="surface-card">
          <text class="setting-title">
            关于你的记忆
          </text><text class="privacy-copy">
            开启后，从聊天提取有原文依据的候选记忆。你可以查看来源；候选未经本人确认，不等同确定事实。
          </text><text class="setting-note">
            {{ !memoryReady ? '记忆设置状态尚未确认。' : memoryEnabled ? '长期记忆已开启。' : '长期记忆未开启。' }} 关闭后停止新提取和后续召回，不删除原文或已有候选。编辑、删除尚未开放。
          </text>
          <AppButton
            v-if="currentUser"
            :loading="memoryBusy"
            :disabled="memoryLoading || !memoryReady"
            :error="!!memoryError"
            secondary
            @click="toggleMemory"
          >
            {{ memoryEnabled ? '关闭长期记忆' : '开启长期记忆' }}
          </AppButton>
          <text
            v-if="memoryError"
            role="alert"
            class="account-error"
          >
            {{ memoryError }}
          </text>
          <AppButton
            v-if="memoryError && !memoryReady"
            secondary
            :loading="memoryLoading"
            @click="readMemoryConsent"
          >
            重新读取记忆设置
          </AppButton>
        </view>
        <text
          v-if="accountError || sessionError"
          role="alert"
          class="account-error"
        >
          {{ accountError || sessionError }}
        </text>
        <AppButton
          v-if="currentUser"
          :loading="busy"
          secondary
          @click="leave"
        >
          {{ busy ? '正在退出…' : '退出登录' }}
        </AppButton>
        <AppButton
          v-else
          secondary
          @click="openLogin"
        >
          登录演示账号
        </AppButton>
      </view>
    </scroll-view>
    <template #footer>
      <BottomTabs />
    </template>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
.settings-content { display: flex; flex-direction: column; gap: 20px; padding-top: 12px; }
.profile { display: flex; gap: 14px; align-items: center; margin-bottom: 8px; }
.profile-avatar { width: 64px; height: 64px; flex-shrink: 0; }
.profile-title, .setting-title { display: block; font-size: 21px; font-weight: 600; }
.setting-note { display: block; font-size: 14px; line-height: 1.7; color: var(--color-muted); margin-top: 8px; }
.font-options { display: flex; gap: 8px; margin: 20px 0 16px; }
.font-options button { flex: 1; min-height: 48px; border: 1px solid var(--color-line); border-radius: 12px; font-size: 16px; }
.font-options button.chosen { color: var(--color-primary-dark); border-color: var(--color-primary); background: var(--color-soft); }
.font-sample { display: block; font-size: var(--font-body); line-height: 1.8; }
.privacy-copy { display: block; margin-top: 12px; line-height: 1.8; }
.account-error { color: var(--color-error); line-height: 1.6; }
</style>
