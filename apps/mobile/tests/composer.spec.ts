import { test, expect } from '@playwright/test';
import path from 'node:path';
import { freshChat, login } from './helpers';

test('suggestions only fill draft; IME Enter never sends; Shift Enter preserves newline', async ({ page }) => {
  await login(page); await freshChat(page);
  let sends = 0;
  page.on('request', request => { if (request.method() === 'POST' && /\/messages$/.test(request.url())) sends++; });
  await expect(page.locator('.suggestion')).toHaveCount(3);
  await page.getByRole('button', { name: '想聊聊今天发生的事', exact: true }).click();
  const input = page.getByRole('textbox', { name: '想对小忆说的话' });
  await expect(input).toHaveValue('想聊聊今天发生的事');
  expect(sends).toBe(0);
  await input.fill('合成输入法测试');
  await input.dispatchEvent('compositionstart', { data: '测试' });
  await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 229, isComposing: true });
  await input.dispatchEvent('keyup', { key: 'Enter', code: 'Enter', isComposing: true });
  expect(sends).toBe(0);
  await input.dispatchEvent('compositionend', { data: '测试' });
  await input.press('End'); await input.press('Shift+Enter');
  await input.pressSequentially('第二行');
  await expect(input).toHaveValue('合成输入法测试\n第二行');
  expect(sends).toBe(0);
  await page.route('**/conversations/*/messages', async route => {
    if (route.request().method() === 'POST') await new Promise(resolve => setTimeout(resolve, 300));
    await route.continue();
  });
  const saved = page.waitForResponse(response => response.request().method() === 'POST' && /\/messages$/.test(response.url()));
  await input.press('Enter');
  await expect(page.getByRole('button', { name: '发送消息', exact: true })).toBeDisabled();
  await expect(page.locator('.message-row.user .message')).toBeVisible();
  await expect(page.getByText('发送中，尚未确认保存', { exact: true })).toBeVisible();
  await input.press('Enter');
  expect((await (await saved).json()).user_message.content).toBe('合成输入法测试\n第二行');
  await expect(page.locator('.message-row.user .message')).toBeVisible();
  await expect(input).toHaveValue('');
  expect(sends).toBe(1);
  await expect(page.locator('.suggestion')).toHaveCount(0);
});

test('network failure retains input and request ID for safe retry', async ({ page }) => {
  await login(page); await freshChat(page);
  const text = `合成失败重试-${Date.now()}`;
  const ids: string[] = [];
  await page.route('**/conversations/*/messages', async route => {
    if (route.request().method() === 'POST') {
      ids.push(route.request().postDataJSON().client_request_id);
      if (ids.length === 1) { await route.abort('failed'); return; }
    }
    await route.continue();
  });
  const input = page.getByRole('textbox', { name: '想对小忆说的话' });
  await input.fill(text); await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByRole('button', { name: '重试发送', exact: true })).toBeVisible();
  await expect(input).toHaveValue(text);
  await page.getByRole('button', { name: '重试发送', exact: true }).click();
  await expect(input).toHaveValue('');
  await expect(page.locator('.message-row.user .message')).toHaveText(text);
  expect(ids).toHaveLength(2); expect(ids[0]).toBe(ids[1]);
});

test('long messages and keyboard-sized viewport retain readable composer and latest reply', async ({ page }, info) => {
  await login(page); await freshChat(page);
  const input = page.getByRole('textbox', { name: '想对小忆说的话' });
  const long = '合成长消息，用于测试排版。'.repeat(60);
  await input.fill(long); await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(input).toHaveValue('');
  await expect(page.locator('.message-row.user .message')).toHaveText(long);
  await expect(page.locator('#chat-tail')).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await input.focus();
  await page.setViewportSize({ width: info.project.use.viewport!.width, height: 470 });
  await expect(page.locator('#chat-tail')).toBeInViewport();
  const composer = await page.locator('.composer').boundingBox();
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(470);
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/keyboard-${info.project.name}.png`) });
});
