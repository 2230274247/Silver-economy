import { test, expect } from '@playwright/test';
import path from 'node:path';
import { freshChat, login } from './helpers';

test('persistent chat, safe reply retry and cross-user denial', async ({ page }, info) => {
  await login(page);
  await freshChat(page);
  const text = `合成持久化-${info.project.name}-${Date.now()}`;
  await page.getByRole('textbox', { name: '想对小忆说的话' }).fill(text);
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByText(text, { exact: true })).toBeVisible();
  await expect(page.getByText('你的消息已保存，模型回复尚未接入。')).toBeVisible();
  const conversation = (await (await page.request.get('/api/v1/conversations?limit=1')).json()).items[0].id;
  const messagesUrl = `/api/v1/conversations/${conversation}/messages`;
  await page.getByRole('button', { name: '重试回复', exact: true }).click();
  await expect(page.getByRole('button', { name: '重试回复', exact: true })).toBeEnabled();
  expect((await (await page.request.get(messagesUrl)).json()).items).toHaveLength(2);
  await page.reload();
  await expect(page.getByText(text, { exact: true })).toBeVisible();
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/chat-persisted-${info.project.name}.png`) });
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await login(page, 1);
  await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  expect((await page.request.get(messagesUrl)).status()).toBe(404);
});
