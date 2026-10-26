import { expect, test } from '@playwright/test';
import path from 'node:path';

test('mobile shell, draft, navigation and font preference', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('界面预览 · 示例对话')).toBeVisible();
  await expect(page.getByText('今天和王姐出去散步了，路上还遇到了老同学。')).toBeVisible();
  await expect(page.getByRole('button', { name: '聊天', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '我的回忆', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '提醒', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await page.locator('.composer').boundingBox())?.height).toBeLessThanOrEqual(64);
  await page.screenshot({ path: path.resolve(`../../docs/demos/T02-chat-${testInfo.project.name}.png`) });
  const input = page.getByRole('textbox', { name: '想对小忆说的话' });
  await input.fill('一段未发送的合成草稿');
  await page.getByRole('button', { name: '我的回忆', exact: true }).click();
  await expect(page.getByText('故事，从一段聊天开始')).toBeVisible();
  await page.getByRole('button', { name: '提醒', exact: true }).click();
  await expect(page.getByText('还没有待办的事')).toBeVisible();
  await page.getByRole('button', { name: '聊天', exact: true }).click();
  await expect(input).toHaveValue('一段未发送的合成草稿');
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByText('当前是界面预览，消息尚未发送。对话功能接入后即可使用。')).toBeVisible();
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await page.getByRole('button', { name: '特大', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('button', { name: '特大', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '聊天', exact: true }).click();
  await expect(page.locator('.phone-shell')).toHaveCSS('font-size', '22px');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.resolve(`../../docs/demos/T02-large-${testInfo.project.name}.png`) });
  expect(errors).toEqual([]);
});

test('keyboard navigation can open and return from chat history', async ({ page }) => {
  await page.goto('/');
  const history = page.getByRole('button', { name: '查看聊天记录' });
  await history.focus();
  await history.press('Enter');
  await expect(page.getByText('每次聊天，都可以接着说')).toBeVisible();
  await page.getByRole('button', { name: '返回聊天' }).press('Enter');
  await expect(page.getByText('界面预览 · 示例对话')).toBeVisible();
});

test('source preview and unavailable voice give honest feedback', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '记忆来源样式预览' }).click();
  await expect(page.getByText('当前没有提取或保存任何记忆。', { exact: false })).toBeVisible();
  await page.getByText('知道了', { exact: true }).click();
  await page.getByRole('button', { name: '语音输入，暂未开放' }).click();
  await expect(page.getByText('语音、图片将在后续版本开放')).toBeVisible();
});

test('reduced motion, touch targets and compact landscape', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/');
  await expect(page.getByRole('button', { name: '打开个人设置' })).toBeVisible();
  const bounds = await page.getByRole('button', { name: '打开个人设置' }).boundingBox();
  expect(bounds?.width).toBeGreaterThanOrEqual(44);
  expect(bounds?.height).toBeGreaterThanOrEqual(44);
  await expect(page.getByRole('button', { name: '我的回忆', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
