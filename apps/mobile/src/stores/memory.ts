export interface Memory {
  id: string; kind: string; key: string; value: string; status: string;
  time_expression: string | null; event_precision: string; extractor_provider: string | null;
  is_synthetic: boolean; revision: number; value_origin: string;
  confirmed_at: string | null; retrieval_allowed: boolean;
}
export function memoryStatus(memory: Memory) {
  const status = ({ candidate: '候选记忆 · 待确认', confirmed: '已确认', active: '当前有效', historical: '历史状态 · 当前已更新', inactive: '已失效' } as Record<string, string>)[memory.status] || memory.status;
  return `${memory.extractor_provider === 'mock' ? 'Mock 抽取' : ''}${memory.extractor_provider === 'mock' && memory.status === 'candidate' ? '候选 · 待确认' : status}${memory.is_synthetic ? ' · Synthetic' : ''}`;
}
