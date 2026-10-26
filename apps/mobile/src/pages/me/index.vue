<script setup lang="ts">
import AccessibleButton from '../../components/AccessibleButton.vue';
import AppButton from '../../components/AppButton.vue';
import AppHeader from '../../components/AppHeader.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import MobileShell from '../../components/MobileShell.vue';
import { fontSize, setFontSize } from '../../stores/ui';
import type { FontSize } from '../../platform/storage';
const sizes: { size: FontSize; label: string }[] = [{ size: 18, label: '标准' }, { size: 20, label: '大号' }, { size: 22, label: '特大' }];
function openLogin() { uni.navigateTo({ url: '/pages/login/index' }); }
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
            后续接入后，你可以查看记忆来源、纠正或删除。聊天原文与长期记忆会分别说明保存方式。
          </text><text class="setting-note">
            当前为界面预览，未保存对话或记忆。
          </text>
        </view>
        <AppButton
          secondary
          @click="openLogin"
        >
          查看登录页面
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
</style>
