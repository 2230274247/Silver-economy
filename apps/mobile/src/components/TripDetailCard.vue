<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue';
import AccessibleButton from './AccessibleButton.vue';
import { labelTextControl } from '../platform/accessibility';
import { openExternalMap } from '../platform/navigation';
import {
  sendTaskFeedback,
  updateProactivePreference,
  updateOutingTask,
  replacementDraft,
  type OutingTask,
} from '../stores/outings';

const props = defineProps<{ task: OutingTask }>();
const emit = defineEmits<{
  updated: [task: OutingTask];
  feedback: [message: string];
}>();

const open = ref(false);
const editing = ref(false);
const busy = ref(false);
const error = ref('');
const feedbackSent = ref('');
const preferenceBusy = ref(false);
const preferenceError = ref('');
const proactiveThreshold = ref(10);
const form = reactive({
  title: '',
  target_at: '',
  access_buffer_minutes: 10,
  contingency_buffer_minutes: 15,
  lead_minutes: 30,
});

const active = computed(() => ['scheduled', 'departed'].includes(props.task.status));

function controlId(field: string) { return `trip-${props.task.id}-${field}`; }
watch([open, editing, () => props.task.kind, () => props.task.status, () => props.task.time_semantics], async () => {
  await nextTick();
  for (const [field, label] of [
    ['threshold', '车程变化通知阈值分钟数'], ['title', '行程名称'], ['time', '新的到达或出发时间'],
    ['access', '修改后的接驳缓冲分钟数'], ['contingency', '修改后的弹性缓冲分钟数'], ['lead', '修改后的提前提醒分钟数'],
  ]) labelTextControl(controlId(field), label, controlId(`${field}-label`));
});

function displayTime(value: string | null) {
  if (!value) return '暂无';
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Hong_Kong',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function localInput(value: string) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Hong_Kong',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(value));
  const valueOf = (type: string) => parts.find(part => part.type === type)?.value ?? '';
  return `${valueOf('year')}-${valueOf('month')}-${valueOf('day')}T${valueOf('hour')}:${valueOf('minute')}`;
}

function startEdit() {
  form.title = props.task.title;
  form.target_at = localInput(props.task.target_at);
  form.access_buffer_minutes = Number(props.task.calculation_basis.inputs?.access_buffer_minutes ?? 10);
  form.contingency_buffer_minutes = Number(props.task.calculation_basis.inputs?.contingency_buffer_minutes ?? 15);
  form.lead_minutes = Number(props.task.calculation_basis.inputs?.lead_minutes ?? 30);
  proactiveThreshold.value = Number(props.task.proactive_change_threshold_minutes ?? 10);
  editing.value = true;
  error.value = '';
}

function purposeLabel(purpose: string) {
  if (purpose === 'internal_refresh') return '出发前路线天气复核';
  if (purpose === 'schedule_change') return '变化提醒';
  return '主要提醒';
}

async function save() {
  if (busy.value || !form.title.trim() || !form.target_at) return;
  busy.value = true;
  error.value = '';
  try {
    const target = new Date(`${form.target_at}:00+08:00`);
    if (Number.isNaN(target.getTime())) throw new Error('请选择有效的北京时间');
    const changed = await updateOutingTask(props.task, {
      title: form.title.trim(),
      target_at: target.toISOString(),
      access_buffer_minutes: Number(form.access_buffer_minutes),
      contingency_buffer_minutes: Number(form.contingency_buffer_minutes),
      lead_minutes: Number(form.lead_minutes),
    });
    editing.value = false;
    emit('updated', changed);
    emit('feedback', '行程时间已更新，新的提醒已重新安排。');
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '行程修改失败';
  } finally {
    busy.value = false;
  }
}

async function feedback(value: 'helpful' | 'not_helpful') {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await sendTaskFeedback(props.task, value);
    feedbackSent.value = value === 'helpful' ? '已记录：提醒有帮助' : '已记录：需要改进';
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '反馈提交失败';
  } finally {
    busy.value = false;
  }
}

async function changePlace() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const draft = await replacementDraft(props.task);
    uni.navigateTo({ url: `/pages/index/index?id=${encodeURIComponent(draft.conversation_id)}` });
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '地点修改草案读取失败，请重试';
  } finally {
    busy.value = false;
  }
}

async function setProactive(enabled: boolean) {
  if (preferenceBusy.value) return;
  preferenceBusy.value = true;
  preferenceError.value = '';
  try {
    const changed = await updateProactivePreference(
      props.task,
      enabled,
      Number(proactiveThreshold.value),
    );
    emit('updated', changed);
    emit(
      'feedback',
      enabled ? '已开启出行变化提醒。' : '已关闭出行变化提醒，普通提醒不受影响。',
    );
  } catch (reason) {
    preferenceError.value = reason instanceof Error ? reason.message : '偏好保存失败';
  } finally {
    preferenceBusy.value = false;
  }
}
</script>

<template>
  <view class="trip-detail">
    <AccessibleButton
      secondary
      :aria-expanded="open"
      @click="open = !open"
    >
      {{ open ? '收起行程详情' : '查看行程详情' }}
    </AccessibleButton>
    <view
      v-if="open"
      class="detail-body"
      data-trip-detail
    >
      <view
        v-if="task.kind === 'outing'"
        class="detail-block"
      >
        <text class="detail-heading">
          路线与来源
        </text>
        <text v-if="task.route_snapshot?.duration_seconds">
          参考路程 {{ Number(task.route_snapshot.distance_m || 0) / 1000 }} 公里，
          约 {{ Math.ceil(Number(task.route_snapshot.duration_seconds) / 60) }} 分钟
        </text>
        <text v-else>
          暂无可靠路线，不虚构车程。
        </text>
        <text>{{ task.route_snapshot?.estimate_basis || '路线来源未提供额外说明' }}</text>
        <text v-if="task.weather_snapshot?.umbrella_advice">
          天气建议：{{ task.weather_snapshot.umbrella_advice }}
        </text>
        <text v-else>
          天气：{{ task.weather_snapshot?.message || '暂无可用依据' }}
        </text>
        <text v-if="task.is_synthetic || task.provider === 'mock'">
          Synthetic / Mock 参考数据，不代表实时结果。
        </text>
        <AccessibleButton
          secondary
          @click="openExternalMap(task.navigation_url)"
        >
          打开高德地图查找目的地
        </AccessibleButton>
        <text v-if="task.status === 'scheduled'">
          修改地点会打开新的核对卡；新卡确认安排前，原提醒保留。确认后原提醒失效。
        </text>
        <AccessibleButton
          v-if="task.status === 'scheduled'"
          secondary
          :loading="busy"
          :disabled="busy"
          @click="changePlace"
        >
          修改地点和交通方式
        </AccessibleButton>
      </view>

      <view class="detail-block">
        <text class="detail-heading">
          安排依据
        </text>
        <text>{{ task.calculation_basis.formula || '已按确认时间安排' }}</text>
        <text>提前提醒：{{ task.calculation_basis.inputs?.lead_minutes ?? '—' }} 分钟</text>
        <text>确认：{{ displayTime(task.confirmed_at) }}</text>
        <text v-if="task.departed_at">
          已出发：{{ displayTime(task.departed_at) }}
        </text>
      </view>

      <view class="detail-block">
        <text class="detail-heading">
          通知记录
        </text>
        <view
          v-for="job in task.notifications"
          :key="job.id"
          class="notification-line"
        >
          <text>{{ purposeLabel(job.purpose) }} · {{ displayTime(job.scheduled_at) }} · {{ job.status }}</text>
          <text v-if="job.purpose === 'internal_refresh'">
            仅复核一次路线与天气；不随每分钟输入持续查询。
          </text>
          <text v-else>
            {{ job.is_mock ? 'Mock 站内通知，不能证明手机收到' : `${job.provider} 已提交，送达未确认` }}
          </text>
          <text v-if="job.error_code">
            原因：{{ job.error_code }}
          </text>
        </view>
      </view>

      <view
        v-if="task.kind === 'outing' && task.status === 'scheduled'"
        class="detail-block"
      >
        <text class="detail-heading">
          出行变化提醒
        </text>
        <text>
          {{ task.proactive_updates_enabled ? '已开启：出发前只复核一次，超过阈值才通知。' : '已关闭：普通提醒仍会按原时间保留。' }}
        </text>
        <label class="field-label">
          <text :id="controlId('threshold-label')">车程变化通知阈值（分钟）</text>
          <input
            :id="controlId('threshold')"
            v-model.number="proactiveThreshold"
            aria-label="车程变化通知阈值分钟数"
            type="number"
            min="5"
            max="60"
          >
        </label>
        <AccessibleButton
          secondary
          :loading="preferenceBusy"
          :disabled="preferenceBusy"
          @click="setProactive(!task.proactive_updates_enabled)"
        >
          {{ task.proactive_updates_enabled ? '关闭出行变化提醒' : '开启出行变化提醒' }}
        </AccessibleButton>
        <text
          v-if="preferenceError"
          role="alert"
          class="detail-error"
        >
          {{ preferenceError }}
        </text>
      </view>

      <view
        v-if="active"
        class="detail-block"
      >
        <AccessibleButton
          v-if="!editing"
          secondary
          @click="startEdit"
        >
          修改行程
        </AccessibleButton>
        <view
          v-else
          class="edit-form"
        >
          <label class="field-label">
            <text :id="controlId('title-label')">行程名称</text>
            <input
              :id="controlId('title')"
              v-model="form.title"
              aria-label="行程名称"
              maxlength="160"
            >
          </label>
          <label class="field-label">
            <text :id="controlId('time-label')">新的时间（北京时间）</text>
            <input
              :id="controlId('time')"
              v-model="form.target_at"
              aria-label="新的到达或出发时间"
              type="datetime-local"
            >
          </label>
          <label
            v-if="task.kind === 'outing' && task.time_semantics === 'arrival'"
            class="field-label"
          >
            <text :id="controlId('access-label')">接驳缓冲（分钟）</text>
            <input
              :id="controlId('access')"
              v-model.number="form.access_buffer_minutes"
              aria-label="修改后的接驳缓冲分钟数"
              type="number"
              min="0"
              max="180"
            >
          </label>
          <label
            v-if="task.kind === 'outing' && task.time_semantics === 'arrival'"
            class="field-label"
          >
            <text :id="controlId('contingency-label')">弹性缓冲（分钟）</text>
            <input
              :id="controlId('contingency')"
              v-model.number="form.contingency_buffer_minutes"
              aria-label="修改后的弹性缓冲分钟数"
              type="number"
              min="0"
              max="180"
            >
          </label>
          <label class="field-label">
            <text :id="controlId('lead-label')">提前提醒（分钟）</text>
            <input
              :id="controlId('lead')"
              v-model.number="form.lead_minutes"
              aria-label="修改后的提前提醒分钟数"
              type="number"
              min="0"
              max="10080"
            >
          </label>
          <view class="form-actions">
            <AccessibleButton
              :loading="busy"
              :disabled="busy"
              @click="save"
            >
              保存行程修改
            </AccessibleButton>
            <AccessibleButton
              secondary
              :disabled="busy"
              @click="editing = false"
            >
              放弃修改
            </AccessibleButton>
          </view>
        </view>
      </view>

      <view class="detail-block">
        <text class="detail-heading">
          这次提醒有帮助吗？
        </text>
        <view class="feedback-actions">
          <AccessibleButton
            secondary
            :loading="busy"
            :disabled="busy || !!feedbackSent"
            @click="feedback('helpful')"
          >
            提醒有帮助
          </AccessibleButton>
          <AccessibleButton
            secondary
            :disabled="busy || !!feedbackSent"
            @click="feedback('not_helpful')"
          >
            需要改进
          </AccessibleButton>
        </view>
        <text
          v-if="feedbackSent"
          class="feedback-note"
        >
          {{ feedbackSent }}
        </text>
      </view>
      <text
        v-if="error"
        role="alert"
        class="detail-error"
      >
        {{ error }}
      </text>
    </view>
  </view>
</template>

<style scoped>
.trip-detail { display: flex; flex-direction: column; gap: 10px; }
.trip-detail button { min-height: 46px; }
.detail-body { display: flex; flex-direction: column; gap: 14px; }
.detail-block { display: flex; flex-direction: column; gap: 8px; padding: 14px; border-radius: 14px; background: var(--color-soft); overflow-wrap: anywhere; }
.detail-heading { font-size: 17px; font-weight: 650; }
.notification-line { display: flex; flex-direction: column; gap: 3px; padding: 8px 0; border-top: 1px solid var(--color-line); }
.notification-line:first-of-type { border-top: 0; }
.edit-form { display: flex; flex-direction: column; gap: 12px; }
.field-label { display: flex; flex-direction: column; gap: 6px; font-size: 15px; }
.field-label input { min-height: 46px; padding: 8px 12px; border: 1px solid var(--color-line); border-radius: 10px; background: var(--color-surface); color: var(--color-text); font: inherit; }
.form-actions,.feedback-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.form-actions button,.feedback-actions button { flex: 1; }
.feedback-note { color: var(--color-primary-dark); }
.detail-error { color: var(--color-error); }
</style>
