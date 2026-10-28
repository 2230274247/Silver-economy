<script setup lang="ts">
withDefaults(defineProps<{ name: string; active?: boolean; size?: number }>(), {
  active: false,
  size: 24,
});
</script>

<template>
  <image
    :src="`/static/icons/${name}${active ? '-active' : ''}.svg`"
    :style="{ width: `${size}px`, height: `${size}px` }"
    mode="aspectFit"
    aria-hidden="true"
    class="app-icon"
  />
</template>

<style scoped>
.app-icon { display: block; flex-shrink: 0; }
</style>
