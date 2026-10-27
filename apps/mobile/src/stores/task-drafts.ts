import { request } from '../platform/network';
import type { Place, MapSnapshot } from './maps';

export interface SchedulePreview {
  request_id: string; draft_revision: number; status: 'ready' | 'confirmed';
  semantics: 'unknown' | 'arrival' | 'departure' | 'at';
  target_at: string; departure_at: string; reminder_at: string;
  route_duration_seconds: number | null; route_distance_m: number | null;
  route_reference_status: string; weather_reference_status: string; weather_advice: string | null;
  formula: string; route_subtracted: boolean; provider: string; is_synthetic: boolean;
  calculated_at: string; expires_at: string; created_at: string;
  inputs: { access_buffer_minutes: number; contingency_buffer_minutes: number; lead_minutes: number };
}

export interface TaskDraft {
  id: string; conversation_id: string; source_message_id: string; last_message_id: string;
  source_excerpt: string; kind: 'outing' | 'reminder'; title: string;
  status: 'draft' | 'confirmed' | 'deferred' | 'scheduled' | 'cancelled' | 'completed'; revision: number;
  target_at: string | null; date_text: string; clock_text: string; period_text: string;
  timezone: string; time_semantics: 'unknown' | 'arrival' | 'departure' | 'at';
  time_reference_at: string; resolved_date: string | null;
  origin: string; destination: string;
  transport: 'unknown' | 'taxi' | 'driving' | 'transit' | 'walking' | 'cycling';
  lead_minutes: number; missing_fields: string[]; confirmed_at: string | null;
  evidence: Record<string, { origin: string; value: unknown }>;
  extractor_provider: string; is_synthetic: boolean;
  scheduling_status: 'not_scheduled' | 'scheduled' | 'cancelled' | 'completed';
  location_consent: boolean; origin_place: Place | null; destination_place: Place | null; map_snapshot: MapSnapshot | null;
  access_buffer_minutes: number; contingency_buffer_minutes: number;
  schedule_preview: SchedulePreview | null; scheduled_task_id: string | null;
}
export interface TaskForm {
  title: string; time_text: string; time_semantics: TaskDraft['time_semantics'];
  origin: string; destination: string; transport: TaskDraft['transport']; lead_minutes: number;
}
export function saveTaskDraft(item: TaskDraft, form: TaskForm) {
  return request<TaskDraft>(`/task-drafts/${item.id}/edit`, 'POST', { ...form, expected_revision: item.revision });
}
export function taskAction(item: TaskDraft, action: 'confirm' | 'defer') {
  return request<TaskDraft>(`/task-drafts/${item.id}/actions`, 'POST', { action, expected_revision: item.revision });
}
export function readTaskDraft(id: string) { return request<TaskDraft>(`/task-drafts/${id}`); }
