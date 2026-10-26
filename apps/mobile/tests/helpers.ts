import { expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

export const accounts: { login_name: string; password: string }[] = JSON.parse(fs.readFileSync(path.resolve('../../.cache/demo-accounts.json'), 'utf8'));
export async function login(page: Page, index = 0) {
  await page.goto('/#/pages/login/index');
  await page.getByRole('textbox', { name: '演示账号', exact: true }).fill(accounts[index].login_name);
  await page.getByLabel('密码', { exact: true }).fill(accounts[index].password);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '想对小忆说的话' })).toBeVisible();
  await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
}
export async function freshChat(page: Page) {
  await page.getByRole('button', { name: '查看聊天记录' }).click();
  await page.getByRole('button', { name: '开始新对话', exact: true }).click();
  await expect(page.getByText('今天想聊些什么？', { exact: true })).toBeVisible();
}
