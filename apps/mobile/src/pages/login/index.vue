<script setup lang="ts">
import { onMounted, ref } from 'vue';
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import MobileShell from '../../components/MobileShell.vue';
import { labelTextControl } from '../../platform/accessibility';
import { login } from '../../stores/session';
const name = ref('');
const password = ref('');
const busy = ref(false);
const error = ref('');
onMounted(() => {
  labelTextControl('login-name', '演示账号');
  labelTextControl('login-password', '密码');
});
async function submit() {
  if (busy.value) return;
  error.value = '';
  if (!name.value.trim() || !password.value) { error.value = '请填写账号和密码'; return; }
  busy.value = true;
  try {
    await login(name.value.trim(), password.value);
    password.value = '';
    uni.reLaunch({ url: '/pages/index/index' });
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : '登录失败，请重试';
  } finally { busy.value = false; }
}
function preview() { uni.reLaunch({ url: '/pages/index/index' }); }
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader title="欢迎你" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content login-content">
        <image
          src="/static/companion.svg"
          class="welcome-avatar"
        />
        <text class="page-title">
          很高兴，听你说说。
        </text><text class="page-description">
          时光有声 · 银发记忆
        </text>
        <view class="surface-card login-form">
          <label for="login-name">演示账号</label><input
            id="login-name"
            v-model="name"
            class="login-input"
            placeholder="请输入演示账号"
            :disabled="busy"
            :maxlength="64"
          >
          <label for="login-password">密码</label><input
            id="login-password"
            v-model="password"
            class="login-input"
            placeholder="请输入演示密码"
            password
            :disabled="busy"
            :maxlength="128"
            confirm-type="done"
            @confirm="submit"
          >
          <text
            v-if="error"
            class="login-error"
            role="alert"
          >
            {{ error }}
          </text>
          <AppButton
            :loading="busy"
            @click="submit"
          >
            {{ busy ? '正在登录…' : '登录' }}
          </AppButton>
        </view>
        <text class="setting-note">
          仅限合成测试账号。账号由运营方在本机创建，此处无需填写任何模型密钥。
        </text>
        <AppButton
          secondary
          @click="preview"
        >
          先看看界面
        </AppButton>
      </view>
    </scroll-view>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
.login-content { text-align: center; display: flex; flex-direction: column; gap: 18px; }
.welcome-avatar { width: 88px; height: 88px; margin: 0 auto; }
.login-form { text-align: left; display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
.login-input { width: 100%; min-height: 48px; padding: 12px; background: var(--color-bg); border-radius: 12px; font-size: 16px; margin-bottom: 8px; }
.setting-note { font-size: 14px; line-height: 1.8; color: var(--color-muted); }
.login-error { color: var(--color-error); font-size: 16px; line-height: 1.6; }
</style>
