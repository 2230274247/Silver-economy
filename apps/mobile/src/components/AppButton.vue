<script setup lang="ts">
import AccessibleButton from './AccessibleButton.vue';
withDefaults(defineProps<{ secondary?: boolean; disabled?: boolean; loading?: boolean }>(), {
  secondary: false,
  disabled: false,
  loading: false,
});
defineEmits<{ click: [] }>();
</script>

<template>
  <AccessibleButton
    class="app-button"
    :class="{ secondary }"
    :disabled="disabled || loading"
    :loading="loading"
    @click="$emit('click')"
  >
    <slot />
  </AccessibleButton>
</template>

<style scoped>
.app-button { display: flex; align-items: center; justify-content: center; min-height: 52px; width: 100%; padding: 12px 18px; border-radius: 16px; color: white; background: var(--color-primary); font-size: var(--font-body); transition: background var(--motion-duration); }
.app-button:not(:disabled):active, .app-button:not(:disabled):hover { background: var(--color-primary-dark); }
.app-button.secondary { color: var(--color-primary-dark); background: var(--color-soft); }
</style>
