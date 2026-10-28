import { test, expect } from '@playwright/test';
import { accounts, login, logout } from './helpers';

test('real login, reload, logout and switch user without draft leakage', async ({ page, context }) => {
  await login(page);
  expect((await context.cookies()).find(cookie => cookie.name === 'silver_session')?.httpOnly).toBe(true);
  await page.getByRole('textbox', { name: '想对小忆说的话' }).fill('A 的未发送合成草稿');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await page.reload(); await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await logout(page);
  await login(page, 1);
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toHaveValue('');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[1].login_name}`)).toBeVisible();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toHaveCount(0);
  await logout(page);
});

test('delayed logout response settles before switching accounts', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '打开个人设置' }).click();
  let logoutResponseFailure: unknown;
  let markSettled = () => {};
  const settled = new Promise<void>(resolve => { markSettled = resolve; });
  await page.route('**/api/v1/auth/logout', async route => {
    const response = await route.fetch();
    const reply = { status: response.status(), headers: response.headers(), body: await response.body() };
    // Simulate the response/cookie race observed on CI, not a longer assertion timeout.
    await new Promise(resolve => setTimeout(resolve, 500));
    try { await route.fulfill(reply); } catch (error) { logoutResponseFailure = error; }
    finally { markSettled(); }
  });
  await logout(page);
  let loginFailure: unknown;
  try { await login(page, 1); } catch (error) { loginFailure = error; }
  await settled;
  expect(loginFailure).toBeUndefined();
  expect(logoutResponseFailure).toBeUndefined();
  const identity = await page.request.get('/api/v1/me');
  expect(identity.status()).toBe(200);
  expect((await identity.json()).login_name).toBe(accounts[1].login_name);
});
