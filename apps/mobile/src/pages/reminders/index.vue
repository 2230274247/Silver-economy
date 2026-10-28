<script setup lang="ts">
import { onMounted, ref } from 'vue';
import AppHeader from '../../components/AppHeader.vue';
import AccessibleButton from '../../components/AccessibleButton.vue';
import BottomTabs from '../../components/BottomTabs.vue';
import EmptyState from '../../components/EmptyState.vue';
import MobileShell from '../../components/MobileShell.vue';
import TripDetailCard from '../../components/TripDetailCard.vue';
import {
  cancelOutingTask,
  completeOutingTask,
  departOutingTask,
  listOutingTasks,
  type OutingTask,
} from '../../stores/outings';

const tasks = ref<OutingTask[]>([]);
const loading = ref(true);
const error = ref('');
const busyId = ref('');

function displayTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Hong_Kong',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function statusLabel(task: OutingTask) {
  if (task.status === 'scheduled') return '待提醒';
  if (task.status === 'departed') return '已出发';
  if (task.status === 'completed') return '已完成';
  return '已取消';
}

function jobLabel(task: OutingTask) {
  const latest = [...task.notifications].reverse().find(item => item.purpose === 'reminder');
  if (!latest) return '尚无通知记录';
  const mock = latest.is_mock ? 'Mock 通知 · ' : '';
  if (latest.status === 'queued') return `${mock}等待后台 Worker`;
  if (latest.status === 'submitted_to_provider') {
    return latest.is_mock
      ? 'Mock 通知 · 已提交模拟供应商，不能证明手机收到'
      : '已提交推送服务商 · 手机送达尚未确认';
  }
  if (latest.status === 'unknown') return '通知结果未知 · 不自动重发';
  if (latest.status === 'missed') return '已错过发送窗口 · 未补发';
  return `通知状态：${latest.status}`;
}

async function load() {
  loading.value = true;
  error.value = '';
  try {
    tasks.value = (await listOutingTasks()).items;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '提醒读取失败';
  } finally {
    loading.value = false;
  }
}

function replaceTask(changed: OutingTask) {
  tasks.value = tasks.value.map(item => item.id === changed.id ? changed : item);
}

function showNotice(message: string) {
  uni.showToast({ title: message, icon: 'none', duration: 2200 });
}

async function act(task: OutingTask, action: 'cancel' | 'complete' | 'depart') {
  if (busyId.value) return;
  if (action === 'cancel' && task.status !== 'scheduled') return;
  if (action === 'complete' && !['scheduled', 'departed'].includes(task.status)) return;
  if (action === 'depart' && task.status !== 'scheduled') return;
  busyId.value = task.id;
  error.value = '';
  try {
    const changed = action === 'cancel'
      ? await cancelOutingTask(task)
      : action === 'depart'
        ? await departOutingTask(task)
        : await completeOutingTask(task);
    replaceTask(changed);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '任务状态更新失败';
  } finally {
    busyId.value = '';
  }
}

onMounted(load);
</script>

<template>
  <MobileShell>
    <template #header>
      <AppHeader title="提醒" />
    </template>
    <scroll-view
      scroll-y
      class="content-scroll"
    >
      <view class="page-content">
        <text class="page-title">
          答应您的事，会认真记着。
        </text><text class="page-description">
          只在您明确确认后安排；路线或模型不会自行创建提醒。
        </text><text class="preview-label">
          通知状态如实显示；Mock 或服务商接受均不代表 Android 手机已送达
        </text>
      </view>
      <view
        v-if="loading"
        class="task-state"
        role="status"
      >
        正在读取持久任务…
      </view>
      <view
        v-if="error"
        class="task-error"
        role="alert"
      >
        <text>{{ error }}</text>
        <AccessibleButton
          :loading="loading"
          @click="load"
        >
          重新读取
        </AccessibleButton>
      </view>
      <view
        v-for="task in tasks"
        :key="task.id"
        :data-task-id="task.id"
        class="reminder-card"
      >
        <text class="reminder-heading">
          {{ task.title }} · {{ statusLabel(task) }}
        </text>
        <text>{{ task.kind === 'outing' ? `${task.origin || '出发地未填'} → ${task.destination || '目的地未填'}` : '时间提醒' }}</text>
        <text v-if="task.kind === 'outing'">
          {{ task.time_semantics === 'arrival' ? '计划到达' : '计划出发' }}：{{ displayTime(task.target_at) }}
        </text>
        <text>{{ task.kind === 'outing' ? '建议出门' : '事项时间' }}：{{ displayTime(task.departure_at) }}</text>
        <text>提醒时间：{{ displayTime(task.reminder_at) }}（北京时间）</text>
        <text class="reminder-note">
          {{ jobLabel(task) }}
        </text>
        <text
          v-if="task.is_synthetic"
          class="reminder-note"
        >
          Synthetic 演示任务
        </text>
        <TripDetailCard
          :task="task"
          @updated="replaceTask"
          @feedback="showNotice"
        />
        <view
          v-if="task.status === 'scheduled' || task.status === 'departed'"
          class="task-actions"
        >
          <AccessibleButton
            :loading="busyId === task.id"
            :disabled="!!busyId"
            @click="act(task, 'complete')"
          >
            标记完成
          </AccessibleButton>
          <AccessibleButton
            v-if="task.status === 'scheduled'"
            :loading="busyId === task.id"
            :disabled="!!busyId"
            @click="act(task, 'depart')"
          >
            我已出发
          </AccessibleButton>
          <AccessibleButton
            v-if="task.status === 'scheduled'"
            :loading="busyId === task.id"
            :disabled="!!busyId"
            @click="act(task, 'cancel')"
          >
            取消提醒
          </AccessibleButton>
        </view>
      </view>
      <EmptyState
        v-if="!loading && !error && !tasks.length"
        icon="bell"
        title="还没有待办的事"
        description="在聊天中说明安排，补全信息并点击“确认并安排提醒”后，任务会持久保存到这里。"
      />
    </scroll-view>
    <template #footer>
      <BottomTabs active="reminders" />
    </template>
  </MobileShell>
</template>

<style scoped>
.content-scroll { height: 0; flex: 1; }
.page-content { padding-bottom: 8px; }
.task-state { padding: 20px; text-align: center; color: var(--color-muted); }
.task-error,.reminder-card { margin: 12px 20px; padding: 16px; border-radius: 18px; background: var(--color-surface); border: 1px solid var(--color-line); display: flex; flex-direction: column; gap: 10px; overflow-wrap: anywhere; }
.task-error { color: var(--color-error); }
.reminder-heading { font-size: 18px; font-weight: 650; }
.reminder-note { color: var(--color-muted); font-size: 15px; line-height: 1.6; }
.task-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.task-actions button,.task-error button { min-height: 46px; padding: 8px 14px; }
</style>
