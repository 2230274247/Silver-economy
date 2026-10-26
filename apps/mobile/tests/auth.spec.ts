import { test, expect } from '@playwright/test';
import { accounts, login } from './helpers';

test('real login, reload, logout and switch user without draft leakage', async ({ page, context }) => {
  await login(page);
  expect((await context.cookies()).find(cookie => cookie.name === 'silver_session')?.httpOnly).toBe(true);
  await page.getByRole('textbox', { name: '想对小忆说的话' }).fill('A 的未发送合成草稿');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await page.reload(); await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await login(page, 1);
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toHaveValue('');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[1].login_name}`)).toBeVisible();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toHaveCount(0);
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
});
