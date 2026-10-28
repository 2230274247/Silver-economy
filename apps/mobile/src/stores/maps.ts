import { request } from '../platform/network';
import { requestId } from '../platform/ids';
import type { TaskDraft } from './task-drafts';

export interface Place {
  id: string; name: string; address: string; district: string; level: string;
  location: string; adcode: string; citycode: string; provider?: string; is_synthetic?: boolean;
}
export interface MapSnapshot {
  provider: string; is_synthetic: boolean; expires_at: string; expired?: boolean;
  route: { distance_m?: number; duration_seconds?: number; estimate_basis?: string; fetched_at?: string; message?: string; status?: string };
  weather: { status: string; reason?: string; date?: string; city?: string; reporttime?: string;
    dayweather?: string; nightweather?: string; umbrella_advice?: string };
}
export interface SearchResult { query_id: string; items: Place[]; provider: string; is_synthetic: boolean; fetched_at: string; expires_at: string }
export function mapsStatus() { return request<{ provider: string; configured: boolean }>('/maps-status'); }
export function locationConsent(item: TaskDraft, enabled: boolean) {
  return request<TaskDraft>(`/task-drafts/${item.id}/location-consent`, 'POST', { expected_revision: item.revision, enabled });
}
export function searchPlaces(item: TaskDraft, field: 'origin' | 'destination', query: string, city: string, search_kind: 'poi' | 'address') {
  return request<SearchResult>(`/task-drafts/${item.id}/places/search`, 'POST', { expected_revision: item.revision, field, query, city, search_kind, client_request_id: requestId() });
}
export function selectPlace(item: TaskDraft, field: 'origin' | 'destination', query_id: string, candidate_id: string) {
  return request<TaskDraft>(`/task-drafts/${item.id}/places/select`, 'POST', { expected_revision: item.revision, field, query_id, candidate_id });
}
export function mapPreview(item: TaskDraft) {
  return request<TaskDraft>(`/task-drafts/${item.id}/map-preview`, 'POST', { expected_revision: item.revision, client_request_id: requestId() });
}
