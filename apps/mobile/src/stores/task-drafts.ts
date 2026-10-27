import { request } from '../platform/network';
import type { Place, MapSnapshot } from './maps';

export interface TaskDraft {
  id: string; conversation_id: string; source_message_id: string; last_message_id: string;
  source_excerpt: string; kind: 'outing' | 'reminder'; title: string;
  status: 'draft' | 'confirmed' | 'deferred'; revision: number;
  target_at: string | null; date_text: string; clock_text: string; period_text: string;
  timezone: string; time_semantics: 'unknown' | 'arrival' | 'departure' | 'at';
  time_reference_at: string; resolved_date: string | null;
  origin: string; destination: string;
  transport: 'unknown' | 'taxi' | 'driving' | 'transit' | 'walking' | 'cycling';
  lead_minutes: number; missing_fields: string[]; confirmed_at: string | null;
  evidence: Record<string, { origin: string; value: unknown }>;
  extractor_provider: string; is_synthetic: boolean; scheduling_status: 'not_scheduled';
  location_consent: boolean; origin_place: Place | null; destination_place: Place | null; map_snapshot: MapSnapshot | null;
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
