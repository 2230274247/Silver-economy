import { expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

export const accounts: { login_name: string; password: string }[] = JSON.parse(fs.readFileSync(path.resolve('../../.cache/ui-accounts.json'), 'utf8'));

export async function resetHealthState(page: Page) {
  const identity = await (await page.request.get('/api/v1/me')).json();
  const mode = await (await page.request.get('/api/v1/model-status')).json();
  expect(identity.login_name).toBe('ui_a'); expect(mode.provider).toBe('mock');
  let cursor: string | null = null;
  do {
    const records = await (await page.request.get(`/api/v1/memories?limit=100${cursor ? `&before_id=${cursor}` : ''}`)).json();
    for (const fact of records.items) {
      if (fact.kind === 'health' && ['candidate', 'active', 'confirmed'].includes(fact.status)) {
        expect((await page.request.post(`/api/v1/memories/${fact.id}/invalidate`, { data: { expected_revision: fact.revision } })).ok()).toBe(true);
      }
    }
    cursor = records.next_cursor;
  } while (cursor);
}
export async function login(page: Page, index = 0) {
  await page.goto('/#/pages/login/index');
  await page.getByRole('textbox', { name: '演示账号', exact: true }).fill(accounts[index].login_name);
  await page.getByLabel('密码', { exact: true }).fill(accounts[index].password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toBeVisible();
  await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
}
export async function logout(page: Page) {
  const completed = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/auth/logout');
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  expect((await completed).status()).toBe(204);
  // Navigation before this response can apply an old cookie clear after the next login.
  await expect(page.getByRole('textbox', { name: '演示账号', exact: true })).toBeVisible();
}
export async function freshChat(page: Page) {
  await page.getByRole('button', { name: '查看聊天记录' }).click();
  await page.getByRole('button', { name: '开始新对话', exact: true }).click();
  await expect(page.getByText('今天想聊些什么？', { exact: true })).toBeVisible();
}
