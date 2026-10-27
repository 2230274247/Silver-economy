<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import AccessibleButton from './AccessibleButton.vue';
import AppButton from './AppButton.vue';
import MapPreviewPanel from './MapPreviewPanel.vue';
import SchedulePreviewPanel from './SchedulePreviewPanel.vue';
import { labelTextControl } from '../platform/accessibility';
import { bindComposer } from '../platform/composer';
import { draftTimeText } from '../platform/task-time';
import { readTaskDraft, saveTaskDraft, taskAction, type TaskDraft } from '../stores/task-drafts';
const props = defineProps<{ item: TaskDraft }>();
const emit = defineEmits<{ changed: [item: TaskDraft] }>();
const busy = ref(false); const error = ref(''); const sourceVisible = ref(false);
const mapBusy = ref(false);
const blocked = computed(() => busy.value || mapBusy.value);
const editing = ref(false);
const form = reactive({ title: '', time_text: '', origin: '', destination: '', lead: '',
  time_semantics: 'unknown' as TaskDraft['time_semantics'], transport: 'unknown' as TaskDraft['transport'] });
const modes: { value: TaskDraft['transport']; label: string }[] = [
  { value: 'taxi', label: '打车' }, { value: 'transit', label: '公交地铁' },
  { value: 'driving', label: '自己开车' }, { value: 'walking', label: '步行' }, { value: 'cycling', label: '骑车' },
];
const controls = [
  ['title', '事项', 'title'], ['time', '日期和时间', 'time_text'], ['origin', '出发地', 'origin'],
  ['destination', '目的地', 'destination'], ['lead', '提前分钟数', 'lead'],
] as const;
let cleanups: (() => void)[] = [];
function cleanup() { cleanups.forEach(fn => fn()); cleanups = []; }
onUnmounted(cleanup);
function controlId(name: string) { return `task-${props.item.id}-${name}`; }
async function bindLabels() {
  await nextTick();
  cleanup();
  for (const [id, label, field] of controls) {
    labelTextControl(controlId(id), label);
    // Match the existing composer/memory editor: H5 input must reach state before an immediate save.
    cleanups.push(bindComposer(controlId(id), () => {}, () => {}, value => { form[field] = value; }, 'input'));
  }
}
async function sync() {
  const item = props.item;
  Object.assign(form, { title: item.title, time_text: draftTimeText(item), origin: item.origin,
    destination: item.destination, time_semantics: item.time_semantics, transport: item.transport,
    lead: String(item.lead_minutes) });
  await bindLabels();
}
onMounted(sync);
watch(() => props.item.revision, sync);
watch(editing, bindLabels);
const dirty = computed(() => form.title !== props.item.title || form.time_text !== draftTimeText(props.item)
  || form.origin !== props.item.origin || form.destination !== props.item.destination
  || form.transport !== props.item.transport || form.time_semantics !== props.item.time_semantics
  || Number(form.lead) !== props.item.lead_minutes);
async function discardEdits() { editing.value = false; await sync(); }
async function run(action: 'save' | 'confirm' | 'defer' | 'reload') {
  if (blocked.value) return;
  busy.value = true; error.value = '';
  try {
    let item = props.item;
    if (action === 'reload') item = await readTaskDraft(item.id);
    else if (action === 'defer') item = await taskAction(item, 'defer');
    else if (action === 'save' || dirty.value) {
      const lead = Number(form.lead);
      if (!form.title.trim()) throw new Error('请填写事项');
      if (!String(form.lead).trim() || !Number.isInteger(lead) || lead < 0 || lead > 10080) throw new Error('提前分钟数需为0到10080的整数');
      item = await saveTaskDraft(item, { title: form.title, time_text: form.time_text,
        time_semantics: form.time_semantics, origin: form.origin, destination: form.destination,
        transport: form.transport, lead_minutes: lead });
      emit('changed', item);
    }
    if (action === 'confirm') {
      if (item.missing_fields.length) throw new Error(`还需要确认：${item.missing_fields.join('、')}`);
      item = await taskAction(item, 'confirm');
      editing.value = false;
    }
    emit('changed', item);
  } catch (failure) { error.value = failure instanceof Error ? failure.message : '草案保存失败，请核对后重试'; }
  finally { busy.value = false; }
}
</script>

<template>
  <view class="task-card">
    <text class="task-heading">
      {{ item.kind === 'outing' ? '出行草案' : '提醒草案' }}{{ item.extractor_provider === 'mock' ? ' · Mock' : '' }}{{ item.is_synthetic ? ' · Synthetic' : '' }}
    </text>
    <text class="task-state">
      {{ item.status === 'scheduled' ? '提醒已安排 · Mock' : item.status === 'cancelled' ? '任务已取消' : item.status === 'completed' ? '任务已完成' : item.status === 'confirmed' ? '信息已确认' : item.status === 'deferred' ? '已暂不安排' : '待核对' }} · {{ item.scheduling_status === 'not_scheduled' ? '尚未调度' : item.scheduling_status }}
    </text>
    <text class="task-note">
      {{ item.status === 'scheduled' ? '任务与提醒已持久保存；当前为 Mock 站内通知，不能证明手机后台已收到。' : item.status === 'confirmed' ? '信息确认不会自动安排提醒；请在下方单独生成并确认计算预览。' : '当前只保存信息。地点、路线和天气需在下方主动核实，调度前还有独立确认。' }}
    </text>
    <view
      v-if="!editing"
      class="task-summary"
    >
      <text>{{ item.title }}</text>
      <text>时间：{{ draftTimeText(item) || '待补充' }}{{ item.kind === 'outing' ? item.time_semantics === 'arrival' ? ' 到达' : item.time_semantics === 'departure' ? ' 出发' : '（待确认到达/出发）' : '' }}（北京时间）</text>
      <text v-if="item.kind === 'outing'">
        {{ item.origin || '出发地待补充' }} → {{ item.destination || '目的地待补充' }} · {{ modes.find(mode => mode.value === item.transport)?.label || '交通方式待确认' }}
      </text>
    </view>
    <view
      v-if="editing"
      class="task-form"
    >
      <label :for="controlId('title')">事项</label>
      <input
        :id="controlId('title')"
        v-model="form.title"
        :disabled="blocked || item.status === 'deferred'"
        :maxlength="160"
      >
      <label :for="controlId('time')">日期和时间（北京时间）</label>
      <input
        :id="controlId('time')"
        v-model="form.time_text"
        placeholder="如：明天上午10点"
        :disabled="blocked || item.status === 'deferred'"
        :maxlength="160"
      >
      <template v-if="item.kind === 'outing'">
        <text>这个时间是？</text>
        <view
          class="task-options"
          role="group"
          aria-label="到达或出发"
        >
          <AccessibleButton
            :aria-pressed="form.time_semantics === 'arrival'"
            :disabled="blocked || item.status === 'deferred'"
            @click="form.time_semantics = 'arrival'"
          >
            到达时间
          </AccessibleButton>
          <AccessibleButton
            :aria-pressed="form.time_semantics === 'departure'"
            :disabled="blocked || item.status === 'deferred'"
            @click="form.time_semantics = 'departure'"
          >
            出发时间
          </AccessibleButton>
        </view>
        <label :for="controlId('origin')">出发地</label>
        <input
          :id="controlId('origin')"
          v-model="form.origin"
          placeholder="从哪里出发？"
          :disabled="blocked || item.status === 'deferred'"
          :maxlength="200"
        >
        <label :for="controlId('destination')">目的地</label>
        <input
          :id="controlId('destination')"
          v-model="form.destination"
          placeholder="要去哪里？"
          :disabled="blocked || item.status === 'deferred'"
          :maxlength="200"
        >
        <text>交通方式</text>
        <view
          class="task-options"
          role="group"
          aria-label="交通方式"
        >
          <AccessibleButton
            v-for="mode in modes"
            :key="mode.value"
            :aria-pressed="form.transport === mode.value"
            :disabled="blocked || item.status === 'deferred'"
            @click="form.transport = mode.value"
          >
            {{ mode.label }}
          </AccessibleButton>
        </view>
      </template>
      <label :for="controlId('lead')">{{ item.kind === 'outing' ? '出门前' : '事项前' }}提前多久提醒（分钟）</label>
      <input
        :id="controlId('lead')"
        v-model="form.lead"
        type="number"
        :disabled="blocked || item.status === 'deferred'"
        :maxlength="5"
      >
    </view>
    <text
      v-if="item.missing_fields.length && item.status === 'draft'"
      class="task-note"
    >
      还需确认：{{ item.missing_fields.join('、') }}
    </text>
    <view
      v-if="error"
      class="task-error"
      role="alert"
    >
      <text>{{ error }}</text>
      <AccessibleButton
        :loading="busy"
        :disabled="mapBusy"
        @click="run('reload')"
      >
        重新读取最新草案
      </AccessibleButton>
    </view>
    <view
      v-if="!['deferred', 'scheduled', 'cancelled', 'completed'].includes(item.status)"
      class="task-actions"
    >
      <AppButton
        v-if="!editing"
        secondary
        :disabled="blocked"
        @click="editing = true"
      >
        补充或修改信息
      </AppButton>
      <AppButton
        v-if="editing"
        secondary
        :loading="busy"
        :disabled="mapBusy"
        :error="!!error"
        @click="run('save')"
      >
        保存修改
      </AppButton>
      <AppButton
        v-if="item.status === 'draft'"
        :loading="busy"
        :disabled="mapBusy || !editing && item.missing_fields.length > 0"
        :error="!!error"
        @click="run('confirm')"
      >
        {{ dirty ? '保存并确认信息' : '确认信息' }}
      </AppButton>
      <AccessibleButton
        v-if="editing"
        :disabled="blocked"
        @click="discardEdits"
      >
        放弃未保存修改
      </AccessibleButton>
      <AccessibleButton
        :loading="busy"
        :disabled="mapBusy"
        @click="run('defer')"
      >
        暂不安排
      </AccessibleButton>
    </view>
    <MapPreviewPanel
      v-if="item.kind === 'outing' && !editing && !['scheduled', 'cancelled', 'completed'].includes(item.status)"
      :item="item"
      :disabled="busy"
      @changed="emit('changed', $event)"
      @busy="mapBusy = $event"
    />
    <SchedulePreviewPanel
      :item="item"
      :disabled="busy || mapBusy"
      @changed="emit('changed', $event)"
      @busy="mapBusy = $event"
    />
    <AccessibleButton
      :aria-expanded="sourceVisible"
      @click="sourceVisible = !sourceVisible"
    >
      {{ sourceVisible ? '收起原话' : '查看原话' }}
    </AccessibleButton>
    <text
      v-if="sourceVisible"
      class="task-source"
    >
      {{ item.source_excerpt }}
    </text>
  </view>
</template>

<style scoped>
.task-card { width: 100%; padding: 18px; margin: 12px 0; border: 1px solid var(--color-line); background: var(--color-surface); border-radius: 18px; display: flex; flex-direction: column; gap: 10px; font-size: 17px; line-height: 1.6; color: var(--color-text); }
.task-summary,.task-form { display: flex; flex-direction: column; gap: 10px; overflow-wrap: anywhere; }
.task-heading { font-size: 19px; font-weight: 650; }.task-state { color: var(--color-primary-dark); font-weight: 600; }.task-note { font-size: 15px; color: #52675f; }
.task-card input { width: 100%; min-height: 48px; padding: 10px; background: var(--color-bg); border: 1px solid #b7cbbf; border-radius: 10px; font-size: 17px; box-sizing: border-box; }
.task-options { display: flex; flex-wrap: wrap; gap: 8px; }.task-options button { padding: 9px 12px; min-height: 46px; border: 1px solid #9db9aa; border-radius: 10px; }
.task-options button[aria-pressed="true"] { background: var(--color-soft); color: var(--color-primary-dark); border-color: var(--color-primary); font-weight: 600; }
.task-actions { display: flex; flex-direction: column; gap: 10px; }.task-actions > button,.task-error button { min-height: 46px; padding: 8px; }
.task-error { color: var(--color-error); display: flex; flex-direction: column; gap: 8px; }.task-source { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; }
</style>
