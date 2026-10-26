<script setup lang="ts">
const props = withDefaults(defineProps<{ disabled?: boolean; loading?: boolean }>(), {
  disabled: false,
  loading: false,
});
const emit = defineEmits<{ click: [] }>();
function activate() {
  if (!props.disabled && !props.loading) emit('click');
}
</script>

<template>
  <button
    class="accessible-button"
    role="button"
    :tabindex="disabled || loading ? -1 : 0"
    :aria-disabled="disabled || loading"
    :disabled="disabled || loading"
    :loading="loading"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <slot />
  </button>
</template>

<style scoped>
.accessible-button { margin: 0; padding: 0; font: inherit; color: inherit; background: transparent; border-radius: 0; line-height: 1.4; cursor: pointer; touch-action: manipulation; }
.accessible-button::after { border: 0; }
.accessible-button:focus-visible { outline: 3px solid var(--color-primary); outline-offset: 3px; }
.accessible-button[aria-disabled="true"] { cursor: not-allowed; opacity: .55; }
</style>
