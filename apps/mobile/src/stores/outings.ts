import { request } from '../platform/network';
import { requestId } from '../platform/ids';
import type { TaskDraft } from './task-drafts';

export interface NotificationJob {
  id: string; purpose: 'reminder' | 'internal_refresh' | 'schedule_change'; status: string; channel: string; scheduled_at: string;
  attempts: number; provider: string; provider_message_id: string | null;
  last_attempt_at: string | null; error_code: string | null;
  completed_at: string | null; is_mock: boolean;
}

export interface RouteSnapshot {
  distance_m?: number;
  duration_seconds?: number;
  estimate_basis?: string;
  status?: string;
  message?: string;
}

export interface WeatherSnapshot {
  status?: string;
  umbrella_advice?: string;
  message?: string;
}

export interface CalculationBasis {
  formula?: string;
  inputs?: {
    access_buffer_minutes?: number;
    contingency_buffer_minutes?: number;
    lead_minutes?: number;
  };
  [key: string]: unknown;
}

export interface OutingTask {
  id: string; draft_id: string; kind: 'outing' | 'reminder'; title: string;
  status: 'scheduled' | 'departed' | 'cancelled' | 'completed';
  revision: number; time_semantics: string; target_at: string; timezone: string;
  origin: string; destination: string; transport: string;
  departure_at: string; reminder_at: string;
  route_snapshot: RouteSnapshot | null;
  weather_snapshot: WeatherSnapshot | null;
  calculation_basis: CalculationBasis;
  provider: string; is_synthetic: boolean; confirmed_at: string;
  proactive_updates_enabled: boolean; proactive_change_threshold_minutes: number;
  proactive_refresh_at: string | null; last_proactive_refresh_at: string | null;
  departed_at: string | null; navigation_url: string;
  cancelled_at: string | null; completed_at: string | null;
  notifications: NotificationJob[];
}

export function previewSchedule(
  item: TaskDraft,
  values: { access_buffer_minutes: number; contingency_buffer_minutes: number; lead_minutes: number },
) {
  return request<TaskDraft>(`/task-drafts/${item.id}/schedule-preview`, 'POST', {
    expected_revision: item.revision,
    client_request_id: requestId(),
    ...values,
  });
}

export function confirmSchedule(
  item: TaskDraft,
  values: { access_buffer_minutes: number; contingency_buffer_minutes: number; lead_minutes: number },
) {
  return request<OutingTask>(`/task-drafts/${item.id}/schedule`, 'POST', {
    expected_revision: item.revision,
    client_request_id: requestId(),
    ...values,
  });
}

export function listOutingTasks() {
  return request<{ items: OutingTask[] }>('/outing-tasks');
}

export function replacementDraft(task: OutingTask) {
  return request<TaskDraft>(`/outing-tasks/${task.id}/replacement-draft`, 'POST', {
    expected_revision: task.revision,
  });
}

export function cancelOutingTask(task: OutingTask) {
  return request<OutingTask>(`/outing-tasks/${task.id}/cancel`, 'POST', {
    expected_revision: task.revision,
  });
}

export function updateOutingTask(
  task: OutingTask,
  values: {
    title: string;
    target_at: string;
    access_buffer_minutes: number;
    contingency_buffer_minutes: number;
    lead_minutes: number;
  },
) {
  return request<OutingTask>(`/outing-tasks/${task.id}`, 'PATCH', {
    expected_revision: task.revision,
    ...values,
  });
}

export function completeOutingTask(task: OutingTask) {
  return request<OutingTask>(`/outing-tasks/${task.id}/complete`, 'POST', {
    expected_revision: task.revision,
  });
}

export function departOutingTask(task: OutingTask) {
  return request<OutingTask>(`/outing-tasks/${task.id}/depart`, 'POST', {
    expected_revision: task.revision,
  });
}

export function sendTaskFeedback(
  task: OutingTask,
  feedback: 'helpful' | 'not_helpful',
) {
  return request<OutingTask>(`/outing-tasks/${task.id}/feedback`, 'POST', {
    expected_revision: task.revision,
    feedback,
    note: '',
  });
}

export function updateProactivePreference(
  task: OutingTask,
  enabled: boolean,
  changeThresholdMinutes: number,
) {
  return request<OutingTask>(`/outing-tasks/${task.id}/proactive-updates`, 'PATCH', {
    expected_revision: task.revision,
    enabled,
    change_threshold_minutes: changeThresholdMinutes,
  });
}
