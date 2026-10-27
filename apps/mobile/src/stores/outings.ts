import { request } from '../platform/network';
import { requestId } from '../platform/ids';
import type { TaskDraft } from './task-drafts';

export interface NotificationJob {
  id: string; status: string; channel: string; scheduled_at: string;
  attempts: number; provider: string; provider_message_id: string | null;
  last_attempt_at: string | null; error_code: string | null;
  completed_at: string | null; is_mock: boolean;
}

export interface OutingTask {
  id: string; draft_id: string; kind: 'outing' | 'reminder'; title: string;
  status: 'scheduled' | 'cancelled' | 'completed';
  revision: number; time_semantics: string; target_at: string; timezone: string;
  origin: string; destination: string; transport: string;
  departure_at: string; reminder_at: string;
  route_snapshot: Record<string, unknown> | null;
  weather_snapshot: Record<string, unknown> | null;
  calculation_basis: Record<string, unknown>;
  provider: string; is_synthetic: boolean; confirmed_at: string;
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

export function cancelOutingTask(task: OutingTask) {
  return request<OutingTask>(`/outing-tasks/${task.id}/cancel`, 'POST', {
    expected_revision: task.revision,
  });
}

export function completeOutingTask(task: OutingTask) {
  return request<OutingTask>(`/outing-tasks/${task.id}/complete`, 'POST', {
    expected_revision: task.revision,
  });
}
