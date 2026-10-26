<script setup lang="ts">
import AppHeader from '../../components/AppHeader.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
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
      <EmptyState
        icon="message-circle"
        title="每次聊天，都可以接着说"
        description="当前是界面预览，没有真实聊天记录。登录与对话接入后，你可以在这里找回之前的聊天。"
      />
    </scroll-view>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
</style>
