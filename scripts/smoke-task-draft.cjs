/** Operator-only single paid request. Never run by automated regression or CI. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium, expect } = createRequire(path.join(root, 'apps/mobile/package.json'))('@playwright/test');
const marker = path.join(root, '.cache/t11a-live-smoke.json');
const report = path.join(root, 'docs/testing/T11A-live.json');

async function main() {
  if (process.env.SILVER_LIVE_SINGLE_REQUEST !== '1') throw new Error('Explicit one-request flag required');
  if (fs.existsSync(marker) || fs.existsSync(report)) throw new Error('Prior attempt exists; inspect it, never automatically resend');
  const accounts = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'));
  const browser = await chromium.launch();
  let outcome = { status: 'not_sent', synthetic: true, started_at: new Date().toISOString(), real_model_calls: 0 };
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
    await page.goto('/#/pages/login/index');
    const mode = await (await page.request.get('/api/v1/model-status')).json();
    if (mode.provider !== 'deepseek' || !mode.configured) throw new Error('Live provider not configured; no request sent');
    await page.getByLabel('演示账号', { exact: true }).fill(accounts[0].login_name);
    await page.getByLabel('密码', { exact: true }).fill(accounts[0].password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.getByRole('button', { name: '查看聊天记录' }).click();
    await page.getByRole('button', { name: '开始新对话', exact: true }).click();
    await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
    await page.getByLabel('想对小忆说的话', { exact: true }).fill('[Synthetic]明天上午十点去张阿姨家做客，记得提醒我。');
    const reply = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(new URL(r.url()).pathname), { timeout: 45000 });
    outcome.status = 'attempt_started';
    fs.writeFileSync(marker, JSON.stringify(outcome));
    // This is the sole operation in this script that may invoke DeepSeek.
    outcome.real_model_calls = 1;
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const response = await reply;
    const data = await response.json();
    outcome.request_id = data.user_message?.client_request_id;
    outcome.conversation_id = new URL(response.url()).pathname.split('/')[4];
    outcome.error_code = data.assistant_message?.error_code ?? data.error?.code ?? null;
    if (response.status() !== 200 || data.provider !== 'deepseek' || data.assistant_message?.status !== 'completed') throw new Error('Live task response failed; no retry');
    const draft = data.assistant_message.task_drafts[0];
    if (!draft || data.assistant_message.task_drafts.length !== 1 || draft.extractor_provider !== 'deepseek' || !draft.is_synthetic) throw new Error('Live task not extracted; no retry');
    expect(draft.missing_fields).toEqual(['到达还是出发', '出发地', '交通方式']);
    expect(draft.destination).toBe('张阿姨家');
    outcome.draft_id = draft.id;
    outcome.initial_missing_fields = draft.missing_fields;
    const card = page.locator('.task-card');
    await expect(card).toContainText('提醒尚未安排');
    await card.getByRole('button', { name: '补充或修改信息', exact: true }).click();
    await card.getByLabel('出发地', { exact: true }).fill('合成公园南门');
    await card.getByRole('button', { name: '到达时间', exact: true }).click();
    await card.getByRole('button', { name: '打车', exact: true }).click();
    await card.getByRole('button', { name: '保存并确认信息', exact: true }).click();
    await expect(card).toContainText('信息已确认');
    await page.reload();
    await expect(card).toContainText('信息已确认');
    const saved = await (await page.request.get(`/api/v1/task-drafts/${draft.id}`)).json();
    expect(saved.scheduling_status).toBe('not_scheduled');
    expect(saved.status).toBe('confirmed');
    expect(saved.origin).toBe('合成公园南门');
    const history = await (await page.request.get(`/api/v1/conversations/${outcome.conversation_id}/messages`)).json();
    expect(history.items.filter(m => m.role === 'user')).toHaveLength(1);
    expect(history.items.find(m => m.role === 'assistant').task_drafts[0].id).toBe(draft.id);
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(root, 'docs/demos/T11A-live-390.png') });
    outcome = { ...outcome, status: 'passed', refresh_persisted: true, scheduling_status: saved.scheduling_status,
      target_at: saved.target_at, timezone: saved.timezone, followup_model_calls: 0 };
  } catch (error) {
    outcome.status = outcome.status === 'not_sent' ? 'not_sent' : 'failed_no_retry';
    throw error;
  } finally {
    if (outcome.real_model_calls) {
      outcome.finished_at = new Date().toISOString();
      fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
      fs.writeFileSync(report, JSON.stringify(outcome, null, 2) + '\n');
    }
    await browser.close();
    console.log(JSON.stringify(outcome));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
