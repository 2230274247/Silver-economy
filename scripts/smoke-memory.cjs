/** One live combined chat+memory request. Synthetic demo account only. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium, expect } = createRequire(path.join(root, 'apps/mobile/package.json'))('@playwright/test');
const marker = path.join(root, '.cache/t07-live-memory.json');

async function main() {
  const verifyExisting = process.env.SILVER_VERIFY_EXISTING_MEMORY === '1';
  if (verifyExisting ? !fs.existsSync(marker) : process.env.SILVER_LIVE_MEMORY_REQUEST !== '1' || fs.existsSync(marker)) throw new Error('Explicit single-request flag required; a prior attempt must never automatically repeat');
  const account = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'))[0];
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
  let outcome = verifyExisting ? JSON.parse(fs.readFileSync(marker, 'utf8')) : { status: 'not_sent', time: new Date().toISOString(), synthetic_test: true };
  let priorConsent = false;
  let authenticated = false;
  try {
    await page.goto('/#/pages/login/index');
    const mode = await (await page.request.get('/api/v1/model-status')).json();
    if (mode.provider !== 'deepseek' || !mode.configured) throw new Error('Live model unavailable; no request sent');
    await page.getByLabel('演示账号', { exact: true }).fill(account.login_name);
    await page.getByLabel('密码', { exact: true }).fill(account.password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page.getByLabel('想对小忆说的话', { exact: true })).toBeVisible();
    authenticated = true;
    priorConsent = (await (await page.request.get('/api/v1/memory-consent')).json()).enabled;
    if (!verifyExisting) {
    if (!priorConsent) {
      await page.getByRole('button', { name: '打开个人设置' }).click();
      await page.getByRole('button', { name: '开启长期记忆', exact: true }).click();
      await page.getByText('允许', { exact: true }).click();
      await expect(page.getByRole('button', { name: '关闭长期记忆', exact: true })).toBeVisible();
      await page.getByRole('button', { name: '聊天', exact: true }).click();
    }
    await page.getByRole('button', { name: '查看聊天记录' }).click();
    await page.getByRole('button', { name: '开始新对话', exact: true }).click();
    await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
    await page.getByLabel('想对小忆说的话', { exact: true }).fill('上个月我膝盖受伤了');
    const saved = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()), { timeout: 45000 });
    outcome.status = 'attempt_started';
    fs.writeFileSync(marker, JSON.stringify(outcome));
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const result = await (await saved).json();
    outcome = { ...outcome, request_id: result.user_message?.client_request_id, message_id: result.user_message?.id, live_requests: 1 };
    if (result.provider !== 'deepseek' || result.user_message?.memory_status !== 'captured' || result.assistant_message?.status !== 'completed') {
      outcome.status = 'failed_no_retry';
      throw new Error(`Combined request failed: ${result.assistant_message?.error_code ?? result.user_message?.memory_status}; no retry`);
    }
    const all = await (await page.request.get('/api/v1/memories?limit=100')).json();
    let found;
    for (const memory of all.items.filter(m => m.extractor_provider === 'deepseek')) {
      const sources = await (await page.request.get(`/api/v1/memories/${memory.id}/sources?limit=100`)).json();
      if (sources.items.some(s => s.message.id === result.user_message.id)) { found = memory; break; }
    }
    if (!found) throw new Error('No grounded persisted candidate from this exact message');
    if (found.event_precision !== 'month' || found.time_expression !== '上个月') throw new Error('Time precision mismatch');
    outcome = { ...outcome, status: 'candidate_persisted_pending_ui', memory_id: found.id, precision: found.event_precision, source_verified: true };
    await expect(page.getByLabel('想对小忆说的话', { exact: true })).toHaveValue('');
    }
    await page.getByRole('button', { name: '我的回忆', exact: true }).click();
    await page.reload();
    const card = page.locator(`#memory-${outcome.memory_id}`);
    await expect(card.locator('.memory-value')).toBeVisible();
    await card.getByRole('button', { name: '查看来源', exact: true }).click();
    await expect(card.locator('.source-card')).toContainText('上个月我膝盖受伤了');
    await page.screenshot({ path: path.join(root, 'docs/demos/T07-memory-live-390.png') });
    outcome.refresh_persisted = true;
    outcome.status = 'passed';
    outcome.ui_verified_without_new_call = verifyExisting;
  } catch (error) {
    if (outcome.status !== 'not_sent' && outcome.status !== 'failed_no_retry') outcome.status = 'ui_verification_failed_no_retry';
    throw error;
  } finally {
    if (outcome.status !== 'not_sent') fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
    if (authenticated) await page.request.post('/api/v1/memory-consent', { data: { enabled: priorConsent } });
    await browser.close();
    console.log(JSON.stringify(outcome));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
