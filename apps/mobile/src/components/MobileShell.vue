<script setup lang="ts">
import { fontStyle } from '../stores/ui';
</script>

<template>
  <view
    class="phone-shell"
    :style="fontStyle"
  >
    <slot name="header" />
    <view class="main-content">
      <slot />
    </view>
    <slot name="footer" />
  </view>
</template>

<style scoped>
.phone-shell { display: flex; flex-direction: column; width: 100%; max-width: 460px; height: 100vh; height: 100dvh; margin: 0 auto; background: var(--color-bg); font-size: var(--font-body); overflow: hidden; padding-top: env(safe-area-inset-top); }
.main-content { min-height: 0; flex: 1; display: flex; flex-direction: column; }
@media (min-width: 600px) { .phone-shell { height: calc(100dvh - 40px); max-height: 980px; margin-top: 20px; border-radius: 30px; border: 1px solid #cdd8d0; box-shadow: 0 16px 60px #2e493617; } }
</style>
