/** Two separately guarded paid requests; default verify mode is strictly read-only. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium, expect } = createRequire(path.join(root, 'apps/mobile/package.json'))('@playwright/test');

async function main() {
  const phase = process.env.SILVER_LIVE_UPDATE_PHASE || 'verify';
  if (!['recovery', 'recall', 'recall-isolated', 'verify'].includes(phase)) throw new Error('Unknown phase');
  const verifiedPhase = fs.existsSync(path.join(root, '.cache/t09-live-recall-isolated.json')) ? 'recall-isolated' : 'recall';
  const marker = path.join(root, `.cache/t09-live-${phase === 'verify' ? verifiedPhase : phase}.json`);
  if (phase !== 'verify' && fs.existsSync(marker)) throw new Error('An attempt already exists; no retry is permitted');
  if (phase === 'recall-isolated') {
    const failed = JSON.parse(fs.readFileSync(path.join(root, '.cache/t09-live-recall.json'), 'utf8'));
    if (failed.status !== 'failed_no_retry') throw new Error('Separate post-isolation check only follows a recorded failed original check');
  }
  const prior = JSON.parse(fs.readFileSync(path.join(root, '.cache/t07-live-memory.json'), 'utf8'));
  if (prior.status !== 'passed') throw new Error('Prior Synthetic source must have passed');
  let recovery;
  if (phase !== 'recovery') {
    recovery = JSON.parse(fs.readFileSync(path.join(root, '.cache/t09-live-recovery.json'), 'utf8'));
    if ((recovery.status !== 'passed' && recovery.repair_status !== 'passed') || !recovery.synthetic_annotated) throw new Error('Recovery must pass (or be repaired from its saved original) and be annotated Synthetic before recall');
  }
  const account = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'))[0];
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
  let outcome = phase === 'verify' ? JSON.parse(fs.readFileSync(marker, 'utf8')) : { status: 'not_sent', phase, synthetic_test: true, time: new Date().toISOString() };
  let consent;
  try {
    await page.goto('/#/pages/login/index');
    const mode = await (await page.request.get('/api/v1/model-status')).json();
    if (mode.provider !== 'deepseek' || !mode.configured) throw new Error('Live provider unavailable');
    await page.getByLabel('演示账号', { exact: true }).fill(account.login_name);
    await page.getByLabel('密码', { exact: true }).fill(account.password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page.getByLabel('想对小忆说的话', { exact: true })).toBeVisible();
    consent = (await (await page.request.get('/api/v1/memory-consent')).json()).enabled;
    if (phase === 'verify') {
      await page.goto(`/#/pages/index/index?id=${outcome.conversation_id}`);
    } else {
      await page.request.post('/api/v1/memory-consent', { data: { enabled: true } });
      if (phase === 'recovery' && !(await page.request.get(`/api/v1/memories/${prior.memory_id}/sources`)).ok()) throw new Error('Prior source unavailable; not sent');
      await page.getByRole('button', { name: '查看聊天记录' }).click();
      await page.getByRole('button', { name: '开始新对话', exact: true }).click();
      await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
      await page.getByLabel('想对小忆说的话', { exact: true }).fill(phase === 'recovery' ? '我的膝盖已经好了' : '我现在膝盖怎么样？');
      const saved = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()), { timeout: 45000 });
      outcome.status = 'attempt_started'; fs.writeFileSync(marker, JSON.stringify(outcome));
      await page.getByRole('button', { name: '发送消息', exact: true }).click();
      const response = await saved; const result = await response.json();
      const reply = result.assistant_message;
      outcome = { ...outcome, request_id: result.user_message?.client_request_id, message_id: result.user_message?.id, conversation_id: new URL(response.url()).pathname.split('/')[4], live_requests: 1 };
      fs.writeFileSync(marker, JSON.stringify(outcome));
      if (reply?.status !== 'completed' || result.provider !== 'deepseek') throw new Error(`Failed: ${reply?.error_code}; no retry`);
      if (phase === 'recovery') {
        const memories = (await (await page.request.get('/api/v1/memories')).json()).items;
        const healed = memories.find(m => m.value === '我的膝盖已经好了');
        const injury = memories.find(m => m.id === prior.memory_id);
        if (!healed || injury?.status !== 'historical') throw new Error('State transition failed; no retry');
        const sources = (await (await page.request.get(`/api/v1/memories/${healed.id}/sources`)).json()).items;
        if (!sources.some(s => s.message.id === outcome.message_id)) throw new Error('Recovery source mismatch');
        outcome = { ...outcome, memory_id: healed.id, previous_memory_id: injury.id, previous_status: injury.status, source_verified: true };
      } else {
        const refs = reply.memory_refs || [];
        if (!refs.some(r => r.memory_id === recovery.memory_id && r.source_message_id === recovery.message_id && r.is_synthetic) || refs.some(r => r.memory_id === prior.memory_id)) throw new Error('Current-state reference mismatch; no retry');
        if (!/好了|恢复|康复/.test(reply.content) || /仍.{0,4}受伤|还.{0,3}受伤/.test(reply.content)) throw new Error('Current-state answer assertion failed; no retry');
        outcome = { ...outcome, memory_id: recovery.memory_id, reference_verified: true, prior_injury_not_retrieved: true };
      }
      outcome.status = 'reply_persisted_pending_ui';
      fs.writeFileSync(marker, JSON.stringify(outcome));
    }
    await page.reload();
    await expect(page.locator('.chat-scroll')).toHaveAttribute('aria-busy', 'false');
    if (phase !== 'recovery') {
      await expect(page.locator('.memory-reference')).toContainText('我的膝盖已经好了');
      await expect(page.locator('.memory-reference')).toContainText('Synthetic');
    }
    await page.screenshot({ path: path.join(root, `docs/demos/T09-${phase === 'verify' ? verifiedPhase : phase}-live-390.png`) });
    outcome = { ...outcome, status: 'passed', refresh_persisted: true };
  } catch (error) {
    if (outcome.status !== 'not_sent') outcome.status = 'failed_no_retry';
    throw error;
  } finally {
    if (outcome.status !== 'not_sent') fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
    if (consent !== undefined) await page.request.post('/api/v1/memory-consent', { data: { enabled: consent } });
    await browser.close(); console.log(JSON.stringify(outcome));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
