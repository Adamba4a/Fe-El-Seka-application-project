// Run with PLAYWRIGHT_MODULE pointing to an installed Playwright module.
// The main app must be running locally. All support submissions are intercepted.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    let status = 503;
    const requests = [];
    await page.route('**/api/support', async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: {
          'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'content-type',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
        } });
        return;
      }
      requests.push(route.request().postDataJSON());
      await route.fulfill({ status, contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ id: requests.at(-1).id }) });
    });
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'عندك مشكلة؟', exact: true }).click();
    const dialog = page.getByRole('dialog');
    assert.equal(await page.locator('html').getAttribute('dir'), 'rtl');
    await dialog.getByRole('button', { name: 'إرسال المشكلة', exact: true }).click();
    await dialog.getByRole('alert').waitFor();
    assert.equal(requests.length, 0);
    await page.locator('#support-email').fill('person@example.com');
    await page.locator('#support-description').fill('مش قادر أكمل التسجيل في التطبيق');
    await dialog.getByRole('button', { name: 'إرسال المشكلة', exact: true }).click();
    await dialog.getByRole('alert').waitFor();
    assert.equal(await page.locator('#support-description').inputValue(), 'مش قادر أكمل التسجيل في التطبيق');
    assert.equal(requests[0].locale, 'ar');
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), false);
    assert.equal(await page.evaluate(() => document.activeElement.textContent), 'عندك مشكلة؟');
    await page.getByRole('button', { name: 'عندك مشكلة؟', exact: true }).click();
    assert.equal(await page.locator('#support-email').inputValue(), 'person@example.com');
    const box = await dialog.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 390 && box.height <= 844);
    await page.screenshot({ path: path.join(__dirname, 'support-ar.png') });
    status = 201;
    await dialog.getByRole('button', { name: 'إرسال المشكلة', exact: true }).click();
    await dialog.getByRole('status').waitFor();
    assert.equal(requests[0].id, requests[1].id, 'retry must keep the same request ID');
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'عندك مشكلة؟', exact: true }).click();
    await dialog.getByRole('button', { name: 'Switch to English', exact: true }).click();
    await page.getByRole('heading', { name: 'Contact support', exact: true }).waitFor();
    assert.equal(await page.locator('html').getAttribute('dir'), 'ltr');
    await page.locator('#support-email').fill('person@example.com');
    await page.locator('#support-description').fill('I cannot complete my signup.');
    status = 429;
    await dialog.getByRole('button', { name: 'Send problem', exact: true }).click();
    await page.getByText('You have sent several reports recently. Please try again in an hour.').waitFor();
    await page.screenshot({ path: path.join(__dirname, 'support-en.png') });
    console.log('PASS: mobile RTL/LTR, validation, failure draft, Escape/focus, retry idempotency, success, language switch, rate limit. No real reports sent.');
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
