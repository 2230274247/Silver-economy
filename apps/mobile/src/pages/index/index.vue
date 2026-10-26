<script setup lang="ts">
const stage = 'T01 · 工程骨架';
</script>

<template>
  <view class="shell">
    <text class="eyebrow">
      时光有声 · 内部演示
    </text>
    <text class="title">
      把生活的片段，慢慢留下。
    </text>
    <view class="notice">
      <text>{{ stage }}</text>
      <text>页面已启动。登录、对话与记忆功能尚未接入。</text>
    </view>
  </view>
</template>

<style scoped>
.shell { max-width: 430px; margin: 0 auto; padding: 32px 24px; }
.eyebrow { display: block; color: #586761; font-size: 16px; }
.title { display: block; margin: 28px 0; font-size: 28px; line-height: 1.6; }
.notice { padding: 24px; border-radius: 16px; background: #fff; line-height: 1.8; }
.notice text { display: block; }
</style>
