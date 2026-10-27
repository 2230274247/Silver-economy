<script setup lang="ts">
import { computed, nextTick, onUnmounted, reactive, ref, watch } from 'vue';
import AccessibleButton from './AccessibleButton.vue';
import AppButton from './AppButton.vue';
import { labelTextControl } from '../platform/accessibility';
import { bindComposer } from '../platform/composer';
import { confirmSchedule, previewSchedule } from '../stores/outings';
import { readTaskDraft, type TaskDraft } from '../stores/task-drafts';

const props = defineProps<{ item: TaskDraft; disabled: boolean }>();
const emit = defineEmits<{ changed: [item: TaskDraft]; busy: [value: boolean] }>();
const busy = ref(false);
const error = ref('');
const form = reactive({ access: '', contingency: '', lead: '' });
const previewDraft = ref<TaskDraft | null>(null);
const blocked = computed(() => busy.value || props.disabled);
const active = computed(() => ['confirmed', 'scheduled', 'cancelled', 'completed'].includes(props.item.status));
const currentDraft = computed(() => previewDraft.value ?? props.item);
const canConfirm = computed(() => currentDraft.value.status === 'confirmed'
  && currentDraft.value.schedule_preview?.status === 'ready');
let cleanups: (() => void)[] = [];

function controlId(name: string) {
  return `schedule-${props.item.id}-${name}`;
}

function cleanup() {
  cleanups.forEach(fn => fn());
  cleanups = [];
}

onUnmounted(cleanup);

async function bindInputs() {
  await nextTick();
  cleanup();
  const labels = [
    ['access', '接驳或步行缓冲分钟数'],
    ['contingency', '弹性缓冲分钟数'],
    ['lead', props.item.kind === 'outing' ? '出门前提前多久提醒（分钟）' : '事项前提前多久提醒（分钟）'],
  ] as const;
  for (const [name, label] of labels) {
    labelTextControl(controlId(name), label);
    cleanups.push(bindComposer(controlId(name), () => {}, () => {},
      value => { form[name] = value; }, 'input'));
  }
}

async function sync() {
  Object.assign(form, {
    access: String(props.item.access_buffer_minutes ?? 10),
    contingency: String(props.item.contingency_buffer_minutes ?? 15),
    lead: String(props.item.lead_minutes ?? 0),
  });
  await bindInputs();
}

watch(() => props.item.revision, sync, { immediate: true });
watch(() => props.item.status, bindInputs);

function values() {
  const access = Number(form.access);
  const contingency = Number(form.contingency);
  const lead = Number(form.lead);
  for (const [label, value] of [['接驳/步行缓冲', access], ['弹性缓冲', contingency]] as const) {
    if (!Number.isInteger(value) || value < 0 || value > 180) {
      throw new Error(`${label}需为 0 到 180 的整数`);
    }
  }
  if (!Number.isInteger(lead) || lead < 0 || lead > 10080) {
    throw new Error('提前提醒需为 0 到 10080 的整数分钟');
  }
  return {
    access_buffer_minutes: access,
    contingency_buffer_minutes: contingency,
    lead_minutes: lead,
  };
}

async function run(action: 'preview' | 'confirm' | 'reload') {
  if (blocked.value) return;
  busy.value = true;
  error.value = '';
  emit('busy', true);
  try {
    if (action === 'preview') {
      const result = await previewSchedule(props.item, values());
      previewDraft.value = result;
      emit('changed', result);
    } else if (action === 'confirm') {
      if (!canConfirm.value) throw new Error('请先生成并核对完整提醒预览');
      await confirmSchedule(currentDraft.value, values());
      emit('changed', await readTaskDraft(props.item.id));
    } else {
      emit('changed', await readTaskDraft(props.item.id));
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '提醒安排未完成，请核对后重试';
  } finally {
    busy.value = false;
    emit('busy', false);
  }
}

function displayTime(value?: string | null) {
  if (!value) return '未知';
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Hong_Kong',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}
</script>

<template>
  <view
    v-if="active"
    class="schedule-panel"
  >
    <text class="schedule-heading">
      计算并安排主动提醒
    </text>
    <text
      v-if="item.status === 'confirmed'"
      class="schedule-note"
    >
      信息确认不会自动安排提醒；请生成预览并再次确认。
    </text>
    <text
      v-if="item.status === 'scheduled'"
      class="schedule-note"
    >
      已进入持久任务和通知队列；当前为 Mock 站内通知，不能证明手机已收到。
    </text>
    <text
      v-else-if="item.status === 'cancelled'"
      class="schedule-note"
    >
      任务已取消；后续未发送的提醒已失效。
    </text>
    <text
      v-else-if="item.status === 'completed'"
      class="schedule-note"
    >
      任务已标记完成；后续未发送的提醒已失效。
    </text>
    <template v-if="item.status === 'confirmed'">
      <template v-if="item.kind === 'outing' && item.time_semantics === 'arrival'">
        <label :for="controlId('access')">接驳或步行缓冲分钟数</label>
        <input
          :id="controlId('access')"
          v-model="form.access"
          type="number"
          :disabled="blocked"
          :maxlength="3"
        >
        <label :for="controlId('contingency')">弹性缓冲分钟数</label>
        <input
          :id="controlId('contingency')"
          v-model="form.contingency"
          type="number"
          :disabled="blocked"
          :maxlength="3"
        >
      </template>
      <label :for="controlId('lead')">
        {{ item.kind === 'outing' ? '出门前' : '事项前' }}提前多久提醒（分钟）
      </label>
      <input
        :id="controlId('lead')"
        v-model="form.lead"
        type="number"
        :disabled="blocked"
        :maxlength="5"
      >
      <AppButton
        secondary
        :loading="busy"
        :disabled="blocked || item.missing_fields.length > 0"
        :error="!!error"
        @click="run('preview')"
      >
        生成提醒预览
      </AppButton>
    </template>
    <view
      v-if="item.schedule_preview"
      class="schedule-result"
    >
      <text>
        {{ item.schedule_preview.is_synthetic ? 'Mock / Synthetic计算预览' : '确定性计算预览' }}
      </text>
      <text>目标时间：{{ displayTime(item.schedule_preview.target_at) }}（北京时间）</text>
      <text v-if="item.kind === 'outing'">
        {{ item.schedule_preview.semantics === 'arrival' ? '建议出门' : '计划出门' }}：{{ displayTime(item.schedule_preview.departure_at) }}
      </text>
      <text>提醒时间：{{ displayTime(item.schedule_preview.reminder_at) }}</text>
      <text
        v-if="item.kind === 'outing' && item.schedule_preview.route_duration_seconds"
        class="schedule-note"
      >
        参考车程：约 {{ Math.ceil(item.schedule_preview.route_duration_seconds / 60) }} 分钟；
        {{ item.schedule_preview.route_subtracted ? '已从到达时间扣除' : '出发时间不重复扣除车程' }}。
      </text>
      <text
        v-if="item.schedule_preview.weather_advice"
        class="schedule-note"
      >
        {{ item.schedule_preview.weather_advice }}
      </text>
      <text
        v-else-if="item.kind === 'outing'"
        class="schedule-note"
      >
        没有可用的当日天气依据，不生成带伞结论。
      </text>
      <text
        v-else
        class="schedule-note"
      >
        没有可用的当日天气依据；普通时间提醒不虚构路线或带伞结论。
      </text>
      <text class="schedule-note">
        预览有效至 {{ displayTime(item.schedule_preview.expires_at) }}；任何时间或路线变化后必须重新计算。
      </text>
    </view>
    <AppButton
      v-if="item.status === 'confirmed'"
      :loading="busy"
      :disabled="blocked || !canConfirm"
      :error="!!error"
      @click="run('confirm')"
    >
      确认并安排提醒
    </AppButton>
    <view
      v-if="error"
      class="schedule-error"
      role="alert"
    >
      <text>{{ error }}</text>
      <AccessibleButton
        :loading="busy"
        :disabled="blocked"
        @click="run('reload')"
      >
        重新读取最新状态
      </AccessibleButton>
    </view>
  </view>
</template>

<style scoped>
.schedule-panel { display: flex; flex-direction: column; gap: 10px; padding-top: 12px; border-top: 1px solid var(--color-line); overflow-wrap: anywhere; }
.schedule-heading { font-size: 18px; font-weight: 650; }
.schedule-note { color: #52675f; font-size: 15px; line-height: 1.6; }
.schedule-panel input { width: 100%; min-height: 48px; padding: 10px; background: var(--color-bg); border: 1px solid #b7cbbf; border-radius: 10px; font-size: 17px; box-sizing: border-box; }
.schedule-result,.schedule-error { display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 12px; background: var(--color-bg); }
.schedule-error { color: var(--color-error); }
.schedule-panel > button,.schedule-error button { min-height: 48px; }
</style>
