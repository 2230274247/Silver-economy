<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue';
import AppButton from './AppButton.vue';
import { request } from '../platform/network';
import { requestId } from '../platform/ids';
import { bindComposer } from '../platform/composer';
import { labelTextControl } from '../platform/accessibility';
import type { Memory } from '../stores/memory';
const props = defineProps<{ memory: Memory }>();
const emit = defineEmits<{ updated: [Memory]; deleted: [string] }>();
const busy = ref(''); const error = ref(''); const editing = ref(false);
const key = ref(''); const value = ref(''); const time = ref('');
const prefix = `edit-memory-${requestId()}`;
const revisions = ref<{ revision: number; action: string; actor: string; created_at: string; before: { value: string; status: string }; after: { value: string; status: string } }[]>([]);
const nextRevision = ref<number | null>(null);
let cleanups: (() => void)[] = [];
function cleanup() { cleanups.forEach(fn => fn()); cleanups = []; }
onUnmounted(cleanup);
async function edit() {
  if (busy.value) return;
  key.value = props.memory.key; value.value = props.memory.value; time.value = props.memory.time_expression || '';
  editing.value = true; error.value = '';
  await nextTick(); cleanup();
  for (const [field, label, target, selector] of [
    ['key', '记忆主题', key, 'input'], ['value', '纠正后的记忆内容', value, 'textarea'], ['time', '原文时间表达', time, 'input'],
  ] as const) {
    labelTextControl(`${prefix}-${field}`, label);
    cleanups.push(bindComposer(`${prefix}-${field}`, () => {}, () => {}, text => { target.value = text; }, selector));
  }
}
function cancel() { if (busy.value) return; editing.value = false; cleanup(); error.value = ''; }
async function mutate(action: string, extra: Record<string, unknown> = {}) {
  if (busy.value) return;
  busy.value = action; error.value = '';
  try {
    const path = `/memories/${props.memory.id}`;
    const payload = { expected_revision: props.memory.revision, ...extra };
    if (action === 'delete') {
      await request(path, 'DELETE', payload); emit('deleted', props.memory.id);
    } else {
      const changed = await request<Memory>(`${path}/${action}`, 'POST', payload);
      emit('updated', changed); revisions.value = []; nextRevision.value = null;
      editing.value = false; cleanup();
    }
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '修改失败，请重试。'; }
  finally { busy.value = ''; }
}
async function remove() {
  if (busy.value) return;
  const result = await uni.showModal({ title: '删除这条长期记忆？', content: '删除后不再用于跨会话回忆。原始聊天和既有回复仍保留；修改审计保留在本机数据库，不再参与检索。', confirmText: '删除记忆', cancelText: '保留' });
  if (result.confirm) await mutate('delete');
}
async function history(more = false) {
  if (busy.value) return;
  busy.value = 'history'; error.value = '';
  try {
    const page = await request<{ items: typeof revisions.value; next_revision: number | null }>(`/memories/${props.memory.id}/revisions${more && nextRevision.value ? `?before_revision=${nextRevision.value}` : ''}`);
    revisions.value = more ? [...revisions.value, ...page.items] : page.items; nextRevision.value = page.next_revision;
    if (!revisions.value.length) error.value = '暂无修改记录；原始依据可在“查看来源”中核对。';
  } catch { error.value = '修改记录读取失败，请再次点击重试。'; }
  finally { busy.value = ''; }
}
function nativeInput(field: 'key' | 'value' | 'time', event: Event) {
  // #ifndef H5
  const text = (event as unknown as { detail: { value: string } }).detail.value;
  ({ key, value, time })[field].value = text;
  // #endif
  void field; void event;
}
const actions: Record<string, string> = { confirm: '确认状态', correct: '用户纠错', invalidate: '设为失效', permission: 'AI使用权限', state_superseded: '新表述更新状态' };
</script>

<template>
  <view class="memory-controls">
    <text class="control-note">
      版本 {{ memory.revision }} · {{ memory.value_origin === 'user_edit' ? '用户亲自修改' : '聊天原文提取' }} · {{ memory.retrieval_allowed ? '允许AI使用（还需全局开启）' : '禁止AI使用' }}
    </text>
    <view
      v-if="!editing"
      class="control-actions"
    >
      <AppButton
        secondary
        :disabled="!!busy"
        :loading="busy === 'confirm'"
        @click="mutate('confirm', { confirmed: !memory.confirmed_at })"
      >
        {{ memory.confirmed_at ? '撤销确认' : '确认记忆' }}
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy"
        @click="edit"
      >
        纠正内容
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy || ['inactive', 'historical'].includes(memory.status)"
        :loading="busy === 'invalidate'"
        @click="mutate('invalidate')"
      >
        设为失效
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy"
        :loading="busy === 'permission'"
        @click="mutate('permission', { allowed: !memory.retrieval_allowed })"
      >
        {{ memory.retrieval_allowed ? '禁止AI使用' : '允许AI使用' }}
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy"
        :loading="busy === 'history'"
        @click="history()"
      >
        修改记录
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy"
        :loading="busy === 'delete'"
        @click="remove"
      >
        删除记忆
      </AppButton>
    </view>
    <view
      v-else
      class="edit-form"
    >
      <text class="control-note">
        确认保存后以你修改的内容为准，原始聊天不改写。失效/历史记录将恢复为已确认；AI使用权限保持原设置。
      </text>
      <text>主题</text><input
        :id="`${prefix}-key`"
        :value="key"
        :maxlength="128"
        :disabled="!!busy"
        @input="nativeInput('key', $event)"
      >
      <text>内容</text><textarea
        :id="`${prefix}-value`"
        :value="value"
        :maxlength="1000"
        :disabled="!!busy"
        auto-height
        @input="nativeInput('value', $event)"
      />
      <text>原文时间表达（可留空）</text><input
        :id="`${prefix}-time`"
        :value="time"
        :maxlength="120"
        :disabled="!!busy"
        @input="nativeInput('time', $event)"
      >
      <text class="control-note">
        保留“上个月”等原表达时，不会改变原来的月份。修改时间表达会按今天重新解析，不能解析的保留为时间未明确。
      </text>
      <AppButton
        :disabled="!!busy || !key.trim() || !value.trim()"
        :loading="busy === 'correct'"
        @click="mutate('correct', { kind: memory.kind, key, value, time_expression: time })"
      >
        保存纠正
      </AppButton>
      <AppButton
        secondary
        :disabled="!!busy"
        @click="cancel"
      >
        取消编辑
      </AppButton>
    </view>
    <view
      v-if="error"
      role="alert"
      class="control-error"
    >
      {{ error }}
    </view>
    <view
      v-for="revision in revisions"
      :key="revision.revision"
      class="revision-card"
    >
      <text>版本 {{ revision.revision }} · {{ actions[revision.action] || revision.action }} · {{ revision.actor === 'user' ? '本人操作' : '原文状态规则' }}</text>
      <text>{{ new Date(revision.created_at).toLocaleString('zh-CN') }}</text>
      <text>之前：{{ revision.before.value }}（{{ revision.before.status }}）</text>
      <text>之后：{{ revision.after.value }}（{{ revision.after.status }}）</text>
    </view>
    <AppButton
      v-if="nextRevision"
      secondary
      :disabled="!!busy"
      :loading="busy === 'history'"
      @click="history(true)"
    >
      更多修改记录
    </AppButton>
  </view>
</template>

<style scoped>
.memory-controls, .edit-form { display: flex; flex-direction: column; gap: 12px; }
.control-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.control-note { color: var(--color-muted); font-size: 15px; line-height: 1.7; }
.control-error { color: #9b3931; line-height: 1.7; }
.edit-form input, .edit-form textarea { box-sizing: border-box; width: 100%; min-height: 52px; padding: 12px; border: 1px solid var(--color-line); border-radius: 12px; background: white; color: var(--color-text); font-size: 18px; }
.edit-form textarea { min-height: 100px; }
.revision-card { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--color-line); padding-top: 12px; font-size: 15px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
