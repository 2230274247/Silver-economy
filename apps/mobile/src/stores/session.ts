import { ref } from 'vue';
import { ApiFailure, request } from '../platform/network';
import { draft } from './ui';

export interface User { id: string; login_name: string }
export const currentUser = ref<User | null>(null);
export const sessionError = ref('');
let revision = 0;

function replaceUser(user: User | null) {
  if (currentUser.value?.id !== user?.id) draft.value = '';
  currentUser.value = user;
  sessionError.value = '';
}
export async function restoreSession() {
  const startedAt = revision;
  try {
    const user = await request<User>('/me');
    if (startedAt === revision) replaceUser(user);
  }
  catch (error) {
    if (startedAt !== revision) return;
    if (error instanceof ApiFailure && error.status === 401) replaceUser(null);
    else sessionError.value = '暂时无法确认登录状态，请检查服务后重试。';
  }
}
export async function login(loginName: string, password: string) {
  revision++;
  const result = await request<{ user: User }>('/auth/login', 'POST', { login_name: loginName, password });
  replaceUser(result.user);
}
export async function logout() {
  revision++;
  await request('/auth/logout', 'POST');
  replaceUser(null);
  draft.value = '';
}
