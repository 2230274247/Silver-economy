import { expect, test } from '@playwright/test';
import path from 'node:path';
import { freshChat, login } from './helpers';

test('mobile shell, draft, real navigation and font preference', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page); await freshChat(page);
  for (const name of ['聊天', '我的回忆', '提醒']) await expect(page.getByRole('button', { name, exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await page.locator('.composer').boundingBox())?.height).toBeLessThanOrEqual(64);
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/chat-${info.project.name}.png`) });
  const input = page.getByRole('textbox', { name: '想对小忆说的话' });
  await input.fill('一段未发送的合成草稿');
  await page.getByRole('button', { name: '我的回忆', exact: true }).click();
  await expect(page.getByText('故事，从一段聊天开始')).toBeVisible();
  await page.getByRole('button', { name: '提醒', exact: true }).click();
  await expect(page.getByText('还没有待办的事')).toBeVisible();
  await page.getByRole('button', { name: '聊天', exact: true }).click();
  await expect(input).toHaveValue('一段未发送的合成草稿');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await page.getByRole('button', { name: '特大', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('button', { name: '特大', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '聊天', exact: true }).click();
  await expect(page.locator('.phone-shell')).toHaveCSS('font-size', '22px');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/large-${info.project.name}.png`) });
  expect(errors).toEqual([]);
});

test('keyboard navigation can open and return from real chat history', async ({ page }) => {
  await login(page);
  const history = page.getByRole('button', { name: '查看聊天记录' });
  await history.focus(); await history.press('Enter');
  await expect(page.getByRole('button', { name: '开始新对话', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '返回聊天' }).press('Enter');
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toBeVisible();
});

test('unavailable voice is disabled and static demonstration messages are absent', async ({ page }) => {
  await login(page); await freshChat(page);
  await expect(page.getByRole('button', { name: '语音输入，暂未开放' })).toBeDisabled();
  await expect(page.getByText('记忆来源样式预览')).toHaveCount(0);
  await expect(page.getByText('今天和王姐出去散步了，路上还遇到了老同学。')).toHaveCount(0);
});

test('reduced motion, touch targets and compact landscape', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 844, height: 390 });
  await login(page);
  const settings = page.getByRole('button', { name: '打开个人设置' });
  await expect(settings).toBeVisible();
  const bounds = await settings.boundingBox();
  expect(bounds?.width).toBeGreaterThanOrEqual(44); expect(bounds?.height).toBeGreaterThanOrEqual(44);
  await expect(page.locator('.companion-image')).toHaveCSS('animation-name', 'none');
  await expect(page.getByRole('button', { name: '我的回忆', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
