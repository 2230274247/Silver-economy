import { computed, ref } from 'vue';
import { readFontSize, saveFontSize, type FontSize } from '../platform/storage';

const fontSize = ref<FontSize>(readFontSize());
export const draft = ref('');
export const fontStyle = computed(() => ({ '--font-body': `${fontSize.value}px` }));
export { fontSize };

export function setFontSize(value: FontSize): void {
  saveFontSize(value);
  fontSize.value = value;
}
