import { test, expect } from '@playwright/test';
import path from 'node:path';
import { login, accounts } from './helpers';

test.afterEach(async ({ page }) => {
  await page.request.post('/api/v1/auth/login', { data: accounts[0] });
  await page.request.post('/api/v1/memory-consent', { data: { enabled: false } });
});

async function createMemory(page: import('@playwright/test').Page, text: string) {
  await page.request.post('/api/v1/memory-consent', { data: { enabled: true } });
  const conversation = await (await page.request.post('/api/v1/conversations')).json();
  const sent = await page.request.post(`/api/v1/conversations/${conversation.id}/messages`, { data: { content: text, client_request_id: crypto.randomUUID() } });
  expect(sent.ok()).toBe(true);
  const list = await (await page.request.get('/api/v1/memories')).json();
  const memory = list.items.find((m: { value: string }) => m.value === text);
  expect(memory).toBeTruthy();
  return { memory, conversation };
}

test('memory controls persist correction, confirmation, privacy, history and safe deletion', async ({ page }, info) => {
  await login(page);
  const original = `我的膝盖受伤了（Synthetic-control-${info.project.name}-${Date.now()}）`;
  const { memory, conversation } = await createMemory(page, original);
  await page.getByRole('button', { name: '我的回忆', exact: true }).click();
  const card = page.locator(`#memory-${memory.id}`);
  await card.getByRole('button', { name: '确认记忆', exact: true }).click();
  await expect(card.getByRole('button', { name: '撤销确认', exact: true })).toBeVisible();
  await card.getByRole('button', { name: '禁止AI使用', exact: true }).click();
  await expect(card).toContainText('禁止AI使用');
  await card.getByRole('button', { name: '允许AI使用', exact: true }).click();
  await card.getByRole('button', { name: '纠正内容', exact: true }).click();
  await card.getByLabel('纠正后的记忆内容', { exact: true }).fill('尚未保存的修改');
  await card.getByRole('button', { name: '取消编辑', exact: true }).click();
  await expect(card.locator('.memory-value')).toHaveText(original);
  await card.getByRole('button', { name: '纠正内容', exact: true }).click();
  const correction = `我的膝盖已经好了（Synthetic-corrected-${info.project.name}-${Date.now()}）`;
  await card.getByLabel('纠正后的记忆内容', { exact: true }).fill(correction);
  // A rejected request keeps the user's edit, permitting explicit retry.
  await page.route(`**/api/v1/memories/${memory.id}/correct`, route => route.abort(), { times: 1 });
  await card.getByRole('button', { name: '保存纠正', exact: true }).click();
  await expect(card.getByRole('alert')).toContainText('网络连接失败');
  await expect(card.getByLabel('纠正后的记忆内容', { exact: true })).toHaveValue(correction);
  await card.getByRole('button', { name: '保存纠正', exact: true }).click();
  await expect(card.locator('.memory-value')).toHaveText(correction);
  await page.reload();
  await expect(card.locator('.memory-value')).toHaveText(correction);
  await card.getByRole('button', { name: '修改记录', exact: true }).click();
  await expect(card.locator('.revision-card').filter({ hasText: '用户纠错' })).toContainText(original);
  await card.getByRole('button', { name: '查看来源', exact: true }).click();
  await expect(card.locator('.source-card')).toContainText(original);
  await card.getByRole('button', { name: '设为失效', exact: true }).click();
  await expect(card.getByRole('button', { name: '设为失效', exact: true })).toBeDisabled();
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/memory-controls-${info.project.name}.png`) });
  await card.getByRole('button', { name: '删除记忆', exact: true }).click();
  await expect(page.getByText('删除后不再用于跨会话回忆。', { exact: false })).toBeVisible();
  await page.getByText('保留', { exact: true }).click();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: '删除记忆', exact: true }).click();
  await page.getByText('删除记忆', { exact: true }).last().click();
  await expect(card).toHaveCount(0);
  expect((await page.request.get(`/api/v1/memories/${memory.id}/sources`)).status()).toBe(404);
  const raw = await (await page.request.get(`/api/v1/conversations/${conversation.id}/messages`)).json();
  expect(raw.items[0].content).toBe(original);
  await page.reload(); await expect(card).toHaveCount(0);
});

test('a recovery updates the current state while the injury stays explicitly historical', async ({ page }, info) => {
  await login(page);
  const text = `我的膝盖受伤了（Synthetic-state-${info.project.name}-${Date.now()}）`;
  const { memory } = await createMemory(page, text);
  await createMemory(page, `我的膝盖已经好了（Synthetic-healed-${info.project.name}-${Date.now()}）`);
  await page.getByRole('button', { name: '我的回忆', exact: true }).click();
  const old = page.locator(`#memory-${memory.id}`);
  await expect(old).toContainText('历史状态 · 当前已更新');
  await old.getByRole('button', { name: '修改记录', exact: true }).click();
  await expect(old.locator('.revision-card')).toContainText('新表述更新状态');
  await page.request.post('/api/v1/auth/login', { data: accounts[1] });
  expect((await page.request.post(`/api/v1/memories/${memory.id}/confirm`, { data: { expected_revision: 2, confirmed: true } })).status()).toBe(404);
  expect((await page.request.get(`/api/v1/memories/${memory.id}/revisions`)).status()).toBe(404);
  await page.reload(); await expect(old).toHaveCount(0);
});
