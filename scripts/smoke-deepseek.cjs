/** Explicit single-request live smoke. Automated regression never executes it. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const mobileRequire = createRequire(path.join(root, 'apps/mobile/package.json'));
const { chromium, expect } = mobileRequire('@playwright/test');
const marker = path.join(root, '.cache/t06-live-smoke.json');

async function main() {
  if (process.env.SILVER_LIVE_SINGLE_REQUEST !== '1') throw new Error('Set SILVER_LIVE_SINGLE_REQUEST=1 for the one-request smoke');
  if (fs.existsSync(marker)) throw new Error('Prior live attempt exists. Inspect its result; do not automatically retry.');
  const accounts = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'));
  const browser = await chromium.launch();
  let outcome = { status: 'not_sent', time: new Date().toISOString() };
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
    await page.goto('http://127.0.0.1:5173/#/pages/login/index');
    const mode = await (await page.request.get('/api/v1/model-status')).json();
    if (mode.provider !== 'deepseek' || !mode.configured) throw new Error('Live API not configured; no request sent');
    await page.getByLabel('演示账号', { exact: true }).fill(accounts[0].login_name);
    await page.getByLabel('密码', { exact: true }).fill(accounts[0].password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.getByRole('button', { name: '查看聊天记录' }).click();
    await page.getByRole('button', { name: '开始新对话', exact: true }).click();
    await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
    await page.getByLabel('想对小忆说的话', { exact: true }).fill('你好，请用一句简短的话打个招呼。');
    const reply = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()), { timeout: 45000 });
    outcome.status = 'attempt_started';
    fs.writeFileSync(marker, JSON.stringify(outcome)); // durable guard before the only send
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const response = await reply;
    const data = await response.json();
    outcome = { ...outcome, request_id: data.user_message?.client_request_id, conversation_id: new URL(response.url()).pathname.split('/')[4], live_requests: 1 };
    if (response.status() !== 200 || data.assistant_message?.status !== 'completed' || data.provider !== 'deepseek') {
      outcome = { ...outcome, status: 'failed_no_retry', error_code: data.assistant_message?.error_code ?? data.error?.code ?? 'UNKNOWN' };
      throw new Error(`Live smoke failed: ${outcome.error_code}; no retry`);
    }
    await expect(page.locator('.message-row.assistant .message')).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`id=${outcome.conversation_id}`));
    await page.reload();
    await expect(page.locator('.message-row.assistant .message')).toBeVisible();
    const conversation = await (await page.request.get('/api/v1/conversations?limit=1')).json();
    const history = await (await page.request.get(`/api/v1/conversations/${conversation.items[0].id}/messages`)).json();
    if (history.items.length !== 2 || history.items[1].content !== data.assistant_message.content) throw new Error('Reload persistence check failed');
    await page.screenshot({ path: path.join(root, 'docs/demos/T06-deepseek-live-390.png') });
    outcome = { ...outcome, status: 'passed', request_id: data.user_message.client_request_id, refresh_persisted: true, live_requests: 1 };
  } finally {
    if (outcome.status !== 'not_sent') fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
    await browser.close();
    console.log(JSON.stringify(outcome));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
