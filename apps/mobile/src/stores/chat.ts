import { ref } from 'vue';
import { request } from '../platform/network';
import { requestId } from '../platform/ids';
import { draft } from './ui';

export interface Conversation { id: string; title: string; created_at: string }
export interface MemoryReference { label: string; memory_id: string; source_message_id: string; conversation_id: string; source_excerpt: string; recorded_at: string; status: string; confirmed: boolean; is_synthetic: boolean; extractor_provider: string | null }
export interface Message {
  id: string; role: 'user' | 'assistant'; content: string; status: string;
  error_code: string | null; created_at: string;
  reply_to_message_id: string | null; client_request_id: string | null;
  provider: string | null;
  memory_status?: string | null;
  memory_refs?: MemoryReference[];
}
interface Page<T> { items: T[]; next_cursor: string | null }
export const activeConversation = ref<Conversation | null>(null);
export const messages = ref<Message[]>([]);
export const conversations = ref<Conversation[]>([]);
export const busy = ref(false);
export const loading = ref(false);
export const chatError = ref('');
export const historyError = ref('');
export const olderCursor = ref<string | null>(null);
export const conversationCursor = ref<string | null>(null);
export const modelMode = ref('checking');
export const modelConfigured = ref(false);
let epoch = 0;
let pending: { content: string; key: string } | null = null;

export function resetChat() {
  epoch++; pending = null;
  activeConversation.value = null; messages.value = []; conversations.value = [];
  busy.value = false; loading.value = false; chatError.value = ''; historyError.value = '';
  olderCursor.value = null; conversationCursor.value = null;
}
export async function loadConversations(more = false) {
  const started = epoch;
  historyError.value = '';
  const cursor = more && conversationCursor.value ? `&before_id=${conversationCursor.value}` : '';
  try {
    const page = await request<Page<Conversation>>(`/conversations?limit=30${cursor}`);
    if (started !== epoch) return;
    conversations.value = more ? [...conversations.value, ...page.items] : page.items;
    conversationCursor.value = page.next_cursor;
  } catch (error) {
    if (started === epoch) historyError.value = error instanceof Error ? error.message : '历史读取失败';
  }
}
export async function loadChat(id?: string, fresh = false) {
  const started = ++epoch;
  messages.value = []; activeConversation.value = null; pending = null;
  chatError.value = ''; loading.value = true; olderCursor.value = null;
  try {
    const mode = await request<{ provider: string; configured: boolean }>('/model-status');
    if (started !== epoch) return;
    modelMode.value = mode.provider; modelConfigured.value = mode.configured;
    if (fresh) return;
    const chosen = id
      ? await request<Conversation>(`/conversations/${id}`)
      : (await request<Page<Conversation>>('/conversations?limit=1')).items[0];
    if (started !== epoch) return;
    if (!chosen) return;
    const history = await request<Page<Message>>(`/conversations/${chosen.id}/messages`);
    if (started !== epoch) return;
    activeConversation.value = chosen; messages.value = history.items; olderCursor.value = history.next_cursor;
  } catch (error) {
    if (started === epoch) chatError.value = error instanceof Error ? error.message : '聊天读取失败';
  } finally { if (started === epoch) loading.value = false; }
}
export async function loadOlder() {
  if (!activeConversation.value || !olderCursor.value || loading.value) return;
  const started = epoch; loading.value = true;
  try {
    const history = await request<Page<Message>>(`/conversations/${activeConversation.value.id}/messages?before_id=${olderCursor.value}`);
    if (started === epoch) { messages.value = [...history.items, ...messages.value]; olderCursor.value = history.next_cursor; }
  } catch (error) { if (started === epoch) chatError.value = error instanceof Error ? error.message : '历史读取失败'; }
  finally { if (started === epoch) loading.value = false; }
}
export async function sendText(content = draft.value, key?: string) {
  if (busy.value || !content.trim()) return false;
  const started = epoch;
  busy.value = true; chatError.value = '';
  const token = key ?? (pending?.content === content ? pending.key : requestId());
  pending = { content, key: token };
  const localId = `sending-${token}`;
  try {
    if (!activeConversation.value) {
      const created = await request<Conversation>('/conversations', 'POST');
      if (started !== epoch) return;
      activeConversation.value = created;
    }
    if (!messages.value.some(message => message.client_request_id === token)) messages.value.push({ id: localId, role: 'user', content, status: 'sending', error_code: null, created_at: new Date().toISOString(), reply_to_message_id: null, client_request_id: token, provider: null });
    const result = await request<{ user_message: Message; assistant_message: Message }>(`/conversations/${activeConversation.value.id}/messages`, 'POST', { content, client_request_id: token });
    if (started !== epoch) return;
    const combined = new Map(messages.value.filter(item => item.id !== localId).map(item => [item.id, item]));
    combined.set(result.user_message.id, result.user_message);
    combined.set(result.assistant_message.id, result.assistant_message);
    messages.value = [...combined.values()];
    if (draft.value === content) draft.value = '';
    pending = null;
    return true;
  } catch (error) {
    if (started === epoch) { messages.value = messages.value.filter(item => item.id !== localId); chatError.value = error instanceof Error ? error.message : '发送失败，输入已保留，请重试'; }
    return false;
  } finally { if (started === epoch) busy.value = false; }
}
export function retryReply(item: Message) {
  const original = messages.value.find(message => message.id === item.reply_to_message_id);
  if (original?.client_request_id) return sendText(original.content, original.client_request_id);
}
