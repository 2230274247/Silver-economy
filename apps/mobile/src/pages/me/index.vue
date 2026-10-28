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
import { downloadAccountExport } from '../../platform/data-export';
import { confirmAction } from '../../platform/confirmation';
const busy = ref(false);
const accountError = ref('');
const memoryEnabled = ref(false);
const memoryBusy = ref(false);
const memoryLoading = ref(true);
const memoryReady = ref(false);
const memoryError = ref('');
type NotificationDevice = {
  id: string;
  platform: string;
  permission_status: string;
  app_version: string;
  device_label: string;
  can_receive: boolean;
  last_seen_at: string | null;
  revoked_at: string | null;
};
const devices = ref<NotificationDevice[]>([]);
const devicesLoading = ref(true);
const devicesError = ref('');
const revokingDevice = ref('');
const exportBusy = ref(false);
const exportError = ref('');
const adminInfo = ref<{ model: string; daily_request_limit: number; daily_token_limit: number; requests_used: number; search_enabled: boolean } | null>(null);
const adminError = ref('');
async function readAdmin() {
  adminInfo.value = null; adminError.value = '';
  if (!currentUser.value?.is_admin) return;
  try { adminInfo.value = await request('/admin/model-status'); }
  catch { adminError.value = '管理员状态读取失败，请重新进入此页。'; }
}
async function readMemoryConsent() {
  memoryLoading.value = true;
  memoryReady.value = false; memoryError.value = '';
  try { if (currentUser.value) { memoryEnabled.value = (await request<{ enabled: boolean }>('/memory-consent')).enabled; memoryReady.value = true; } }
  catch { memoryError.value = '记忆设置读取失败，请重试。'; }
  finally { memoryLoading.value = false; }
}
async function readDevices() {
  devicesLoading.value = true;
  devicesError.value = '';
  try {
    if (currentUser.value) devices.value = (await request<{ items: NotificationDevice[] }>('/notification-devices')).items;
    else devices.value = [];
  } catch {
    devicesError.value = '通知设备读取失败，请稍后重试。';
  } finally {
    devicesLoading.value = false;
  }
}
onShow(async () => { await Promise.all([readMemoryConsent(), readDevices(), readAdmin()]); });
async function toggleMemory() {
  if (memoryBusy.value || memoryLoading.value || !memoryReady.value) return;
  memoryBusy.value = true; memoryError.value = '';
  try {
    if (!memoryEnabled.value) {
      const choice = await confirmAction({ title: '开启长期记忆', content: '允许从聊天提取有原文依据的候选记忆，并在后续会话检索使用。候选未经本人确认，回复会提供来源供核对。可以随时关闭；关闭不会删除聊天或已有记忆。', confirmText: '允许', cancelText: '暂不' });
      if (!choice.confirm) return;
    }
    memoryEnabled.value = (await request<{ enabled: boolean }>('/memory-consent', 'POST', { enabled: !memoryEnabled.value })).enabled;
  } catch { memoryError.value = '记忆设置保存失败，请重试。'; }
  finally { memoryBusy.value = false; }
}
const sizes: { size: FontSize; label: string }[] = [{ size: 18, label: '标准' }, { size: 20, label: '大号' }, { size: 22, label: '特大' }];
function openLogin() { uni.navigateTo({ url: '/pages/login/index' }); }
function openMemories() { uni.redirectTo({ url: '/pages/timeline/index' }); }
function openChat() { uni.redirectTo({ url: '/pages/index/index' }); }
async function revoke(device: NotificationDevice) {
  if (revokingDevice.value || device.revoked_at) return;
  const choice = await confirmAction({
    title: '撤回这台设备',
    content: '撤回后，未来提醒将不再尝试发送到这台设备。',
    confirmText: '撤回',
    cancelText: '暂不',
  });
  if (!choice.confirm) return;
  revokingDevice.value = device.id;
  devicesError.value = '';
  try {
    const updated = await request<NotificationDevice>(`/notification-devices/${device.id}`, 'DELETE');
    devices.value = devices.value.map(item => item.id === updated.id ? updated : item);
  } catch {
    devicesError.value = '设备撤回失败，请重试。';
  } finally {
    revokingDevice.value = '';
  }
}
async function exportData() {
  if (exportBusy.value) return;
  exportBusy.value = true;
  exportError.value = '';
  try {
    await downloadAccountExport();
    uni.showToast({ title: '数据已导出', icon: 'success' });
  } catch (reason) {
    exportError.value = reason instanceof Error ? reason.message : '数据导出失败，请重试。';
  } finally {
    exportBusy.value = false;
  }
}
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
        <view
          v-if="currentUser?.is_admin"
          class="settings-card"
        >
          <text class="page-title">
            管理员
          </text>
          <text
            v-if="adminInfo"
            class="setting-note"
          >
            模型：{{ adminInfo.model }} · 联网查询{{ adminInfo.search_enabled ? '已开启' : '已关闭' }}。
            独立管理员额度：每日 {{ adminInfo.daily_request_limit }} 次请求、{{ adminInfo.daily_token_limit }} 预留 tokens；今日已用 {{ adminInfo.requests_used }} 次。
          </text>
          <text
            v-if="adminError"
            role="alert"
          >
            {{ adminError }}
          </text>
        </view>
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
            {{ !memoryReady ? '记忆设置状态尚未确认。' : memoryEnabled ? '长期记忆已开启。' : '长期记忆未开启。' }} 关闭后停止新提取和后续召回，不删除原文或已有候选。可进入“我的回忆”查看来源、纠错、删除或逐条停止使用。
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
          <AppButton
            v-if="currentUser"
            secondary
            @click="openMemories"
          >
            管理记忆和来源
          </AppButton>
        </view>
        <view
          v-if="currentUser"
          class="surface-card"
        >
          <text class="setting-title">
            位置与通知授权
          </text><text class="privacy-copy">
            位置只在你为本次出行草案明确开启后，用于地点、路线和天气查询；不读取设备 GPS。可在聊天中的出行卡撤回授权，撤回会清除所选坐标、路线和天气缓存。Android 通知设备可在这里单独撤回。
          </text>
          <text
            v-if="devicesLoading"
            class="setting-note"
            role="status"
          >
            正在读取通知设备…
          </text>
          <text
            v-else-if="!devices.length"
            class="setting-note"
          >
            当前没有已登记的 Android 通知设备。H5 页面不能替代 Android 后台通知验收。
          </text>
          <view
            v-for="device in devices"
            :key="device.id"
            class="device-row"
          >
            <view>
              <text class="device-name">
                {{ device.device_label || 'Android 设备' }}
              </text>
              <text class="setting-note">
                {{ device.revoked_at ? '已撤回' : device.can_receive ? '通知已授权' : '通知未授权' }} · {{ device.app_version || '版本未知' }}
              </text>
            </view>
            <AccessibleButton
              class="text-action"
              :disabled="!!device.revoked_at || !!revokingDevice"
              :loading="revokingDevice === device.id"
              @click="revoke(device)"
            >
              {{ device.revoked_at ? '已撤回' : '撤回' }}
            </AccessibleButton>
          </view>
          <text
            v-if="devicesError"
            role="alert"
            class="account-error"
          >
            {{ devicesError }}
          </text>
          <AppButton
            secondary
            :loading="devicesLoading"
            @click="readDevices"
          >
            重新读取设备
          </AppButton>
          <AppButton
            secondary
            @click="openChat"
          >
            去聊天查看出行卡
          </AppButton>
        </view>
        <view
          v-if="currentUser"
          class="surface-card"
        >
          <text class="setting-title">
            隐私与我的数据
          </text><text class="privacy-copy">
            可下载本人聊天、长期记忆及其来源、行程、提醒、通知状态和脱敏设备信息的 JSON 文件。密码、登录令牌、推送客户端 ID、设备指纹、模型原文和其他用户数据不会包含在文件中。
          </text>
          <AppButton
            :loading="exportBusy"
            @click="exportData"
          >
            {{ exportBusy ? '正在准备导出…' : '导出我的数据' }}
          </AppButton>
          <text
            v-if="exportError"
            role="alert"
            class="account-error"
          >
            {{ exportError }}
          </text>
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
.device-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 14px 0; padding: 14px; border: 1px solid var(--color-line); border-radius: 14px; }
.device-name { display: block; font-size: 17px; font-weight: 600; }
.text-action { min-width: 64px; min-height: 44px; color: var(--color-primary-dark); }
.surface-card :deep(.app-button + .app-button) { margin-top: 10px; }
</style>
