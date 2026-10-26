<script setup lang="ts">
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import MobileShell from '../../components/MobileShell.vue';
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
            class="login-input"
            placeholder="账号功能接入后开放"
            disabled
          >
          <label for="login-password">密码</label><input
            id="login-password"
            class="login-input"
            placeholder="请勿输入真实密码"
            password
            disabled
          >
          <AppButton disabled>
            登录暂未开放
          </AppButton>
        </view>
        <text class="setting-note">
          内部演示，仅使用虚构资料。当前可先预览页面，不会连接模型或保存聊天。
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
</style>
