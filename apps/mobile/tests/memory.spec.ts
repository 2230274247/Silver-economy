import { test, expect } from '@playwright/test';
import path from 'node:path';
import { freshChat, login } from './helpers';

test('memory consent read failure is retryable and cancelling never grants permission', async ({ page }) => {
  await login(page);
  let reads = 0; let writes = 0;
  await page.route('**/api/v1/memory-consent', async route => {
    if (route.request().method() === 'GET' && ++reads === 1) { await route.abort(); return; }
    if (route.request().method() === 'POST') writes++;
    await route.continue();
  });
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText('记忆设置读取失败，请重试。')).toBeVisible();
  await expect(page.getByText(/记忆设置状态尚未确认/)).toBeVisible();
  await expect(page.getByRole('button', { name: '开启长期记忆', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '重新读取记忆设置', exact: true }).click();
  await page.getByRole('button', { name: '开启长期记忆', exact: true }).click();
  await page.getByText('暂不', { exact: true }).click();
  await expect(page.getByRole('button', { name: '开启长期记忆', exact: true })).toBeEnabled();
  expect(writes).toBe(0);
});

test('memory consent, grounded candidate, source and reload use real MySQL with Mock', async ({ page }, info) => {
  await login(page);
  try {
    await page.getByRole('button', { name: '打开个人设置' }).click();
    await page.getByRole('button', { name: '开启长期记忆', exact: true }).click();
    await page.getByText('允许', { exact: true }).click();
    await expect(page.getByRole('button', { name: '关闭长期记忆', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '聊天', exact: true }).click();
    await freshChat(page);
    const text = `上个月我膝盖受伤了（Synthetic-${info.project.name}-${Date.now()}）`;
    await page.getByLabel('想对小忆说的话', { exact: true }).fill(text);
    const saved = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()));
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const result = await (await saved).json();
    expect(result.user_message.memory_status).toBe('captured');
    expect(result.assistant_message.provider).toBe('mock');
    await expect(page.getByLabel('想对小忆说的话', { exact: true })).toHaveValue('');
    await page.getByRole('button', { name: '我的回忆', exact: true }).click();
    const card = page.locator('.memory-card').filter({ hasText: text });
    await expect(card.locator('.memory-value')).toHaveText(text);
    await page.reload();
    await expect(card.locator('.memory-value')).toHaveText(text);
    await card.getByRole('button', { name: '查看来源', exact: true }).click();
    await card.getByRole('button', { name: '查看来源', exact: true }).hover();
    await expect(card.getByRole('button', { name: '查看来源', exact: true })).toHaveCSS('background-color', 'rgb(220, 232, 223)');
    await expect(card.locator('.source-card')).toContainText(`原文：${text}`);
    await expect(card).toContainText('Mock 抽取候选 · 待确认');
    await expect(card).toContainText('月份');
    await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/memory-${info.project.name}.png`) });
    await card.getByRole('button', { name: '返回原会话', exact: true }).click();
    await expect(page.locator('.message-row.user .message')).toHaveText(text);
  } finally {
    expect((await page.request.post('/api/v1/memory-consent', { data: { enabled: false } })).ok()).toBe(true);
  }
});
