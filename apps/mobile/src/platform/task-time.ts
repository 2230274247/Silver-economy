import type { TaskDraft } from '../stores/task-drafts';

// T11A explicitly uses Hong Kong/Beijing time. No browser-only API; other zones follow in settings.
export function draftTimeText(item: TaskDraft) {
  if (item.target_at) return new Date(new Date(item.target_at).getTime() + 8 * 3600000).toISOString().slice(0, 16).replace('T', ' ');
  if (item.resolved_date && item.clock_text) return `${item.resolved_date} ${item.period_text}${item.clock_text}`;
  const edit = item.evidence.time_text;
  return edit?.origin === 'user_edit' && typeof edit.value === 'string'
    ? edit.value : `${item.date_text}${item.period_text}${item.clock_text}`;
}
