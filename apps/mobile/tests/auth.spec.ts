import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('real login, reload, logout and switch user without draft leakage', async ({ page, context }, info) => {
  const accounts: { login_name: string; password: string }[] = JSON.parse(fs.readFileSync(path.resolve('../../.cache/demo-accounts.json'), 'utf8'));
  async function signIn(index: number) {
    await page.getByRole('textbox', { name: '演示账号', exact: true }).fill(accounts[index].login_name);
    await page.getByLabel('密码', { exact: true }).fill(accounts[index].password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page.getByText('界面预览 · 示例对话')).toBeVisible();
  }
  await page.goto('/#/pages/login/index');
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/login-${info.project.name}.png`) });
  await signIn(0);
  const cookies = await context.cookies();
  expect(cookies.find(cookie => cookie.name === 'silver_session')?.httpOnly).toBe(true);
  await page.getByRole('textbox', { name: '想对小忆说的话' }).fill('A 的未发送合成草稿');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await page.reload();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toBeVisible();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await signIn(1);
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toHaveValue('');
  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText(`已登录：${accounts[1].login_name}`)).toBeVisible();
  await expect(page.getByText(`已登录：${accounts[0].login_name}`)).toHaveCount(0);
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
});
