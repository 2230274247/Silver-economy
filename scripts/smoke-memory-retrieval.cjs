/** One live recall request against the prior persisted Synthetic memory. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium, expect } = createRequire(path.join(root, 'apps/mobile/package.json'))('@playwright/test');
const marker = path.join(root, '.cache/t08-live-retrieval.json');

async function main() {
  const verifyExisting = process.env.SILVER_VERIFY_EXISTING_RETRIEVAL === '1';
  if (verifyExisting ? !fs.existsSync(marker) : process.env.SILVER_LIVE_RETRIEVAL_REQUEST !== '1' || fs.existsSync(marker)) throw new Error('Single-request flag required; an existing attempt may only be verified without sending');
  const prior = JSON.parse(fs.readFileSync(path.join(root, '.cache/t07-live-memory.json'), 'utf8'));
  if (prior.status !== 'passed') throw new Error('T07 source has not passed');
  const account = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'))[0];
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
  let outcome = verifyExisting ? JSON.parse(fs.readFileSync(marker, 'utf8')) : { status: 'not_sent', time: new Date().toISOString(), synthetic_test: true };
  let authenticated = false; let priorConsent = false;
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
      const source = await page.request.get(`/api/v1/memories/${prior.memory_id}/sources`);
      if (!source.ok()) throw new Error('Persisted prior source unavailable');
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
      await page.getByLabel('想对小忆说的话', { exact: true }).fill('你还记得我的膝盖之前发生了什么事吗？');
      const saved = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()), { timeout: 45000 });
      outcome.status = 'attempt_started'; fs.writeFileSync(marker, JSON.stringify(outcome));
      await page.getByRole('button', { name: '发送消息', exact: true }).click();
      const response = await saved; const result = await response.json();
      outcome = { ...outcome, live_requests: 1, request_id: result.user_message?.client_request_id, conversation_id: new URL(response.url()).pathname.split('/')[4] };
      const reply = result.assistant_message;
      if (reply?.status !== 'completed' || result.provider !== 'deepseek') throw new Error(`Live recall failed: ${reply?.error_code}; no retry`);
      const reference = reply.memory_refs.find(ref => ref.memory_id === prior.memory_id && ref.source_message_id === prior.message_id);
      if (!reference || !reference.is_synthetic || !/膝盖/.test(reply.content) || !/受伤/.test(reply.content)) throw new Error('Reply/source recall assertion failed; no retry');
      outcome = { ...outcome, status: 'reply_persisted_pending_ui', memory_id: prior.memory_id, source_message_id: prior.message_id, reference_verified: true };
      await expect(page).toHaveURL(new RegExp(`id=${outcome.conversation_id}`));
    } else {
      await page.goto(`/#/pages/index/index?id=${outcome.conversation_id}`);
    }
    await page.reload();
    await expect(page.locator('.memory-reference')).toContainText('上个月我膝盖受伤了');
    await expect(page.locator('.memory-reference')).toContainText('Synthetic');
    await page.screenshot({ path: path.join(root, 'docs/demos/T08-retrieval-live-390.png') });
    outcome = { ...outcome, status: 'passed', refresh_persisted: true, new_login_and_conversation: true };
  } catch (error) {
    if (outcome.status !== 'not_sent') outcome.status = 'failed_no_retry';
    throw error;
  } finally {
    if (outcome.status !== 'not_sent') fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
    if (authenticated) await page.request.post('/api/v1/memory-consent', { data: { enabled: priorConsent } });
    await browser.close(); console.log(JSON.stringify(outcome));
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
