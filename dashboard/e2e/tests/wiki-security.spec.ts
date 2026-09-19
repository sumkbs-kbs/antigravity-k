import { expect, test } from '@playwright/test';

const securityDocument = [
  '# 위키 보안 검증',
  '',
  '- 한국어 목록',
  '- [안전한 링크](https://example.com/safe?a=1#b)',
  '',
  '```typescript',
  'const safe = true;',
  '```',
  '',
  '<h2 id="qa-injected">injected</h2>',
  '<img src="x" onerror="window.__agkWikiXss = true">',
  '<script>window.__agkWikiXss = true</script>',
  '<iframe src="https://example.com"></iframe>',
  '<svg><script>window.__agkWikiXss = true</script></svg>',
  '',
  '[script](javascript:window.__agkWikiXss=true) [data](data:text/html,<script>alert(1)</script>)',
  '[breakout](https://example.com/ "onmouseover="alert(1))',
].join('\n');

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('ag_access_token', 'e2e-token'));
  await page.route(/\/api\/session\/info(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, session: { subject: 'e2e' } }),
  }));
  await page.route(/\/api\/vault\/config(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, vault_path: '/e2e/wiki' }),
  }));
  await page.route(/\/api\/vault\/tree(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      vault_path: '/e2e/wiki',
      tree: [{ name: 'security.md', path: 'security.md', type: 'file' }],
    }),
  }));
  await page.route(/\/api\/vault\/read(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, content: securityDocument, metadata: {} }),
  }));
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 0 }),
  }));
  await page.route(/\/health(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'ok', backends: {} }),
  }));
});

test('renders safe Wiki Markdown and keeps injected HTML inactive', async ({ page }, testInfo) => {
  await page.goto('/wiki');

  const body = page.locator('#wiki-body');
  await expect(body).toBeVisible();
  await page.getByRole('button', { name: '📄 security.md' }).click();
  await expect(page.getByRole('heading', { name: '위키 보안 검증' })).toBeVisible();
  await expect(body.getByText('한국어 목록')).toBeVisible();
  await expect(page.getByRole('link', { name: '안전한 링크' })).toHaveAttribute(
    'href',
    'https://example.com/safe?a=1#b',
  );
  await expect(body.locator('code').last()).toContainText('const safe = true;');

  await expect(page.locator('#qa-injected')).toHaveCount(0);
  await expect(body.locator('script, iframe, svg')).toHaveCount(0);
  await expect(page.locator('[onerror], [onmouseover]')).toHaveCount(0);
  await expect(page.locator('a[href^="javascript:"], a[href^="data:"]')).toHaveCount(0);
  expect(await page.evaluate(() => window.__agkWikiXss)).toBeUndefined();

  const summary = await page.evaluate(() => ({
    activeElements: document.querySelector('#wiki-body')?.querySelectorAll('script, iframe, svg').length ?? -1,
    eventHandlers: document.querySelector('#wiki-body')?.querySelectorAll('[onerror], [onmouseover]').length ?? -1,
    unsafeLinks: document.querySelector('#wiki-body')?.querySelectorAll('a[href^="javascript:"], a[href^="data:"]').length ?? -1,
  }));
  expect(summary).toEqual({ activeElements: 0, eventHandlers: 0, unsafeLinks: 0 });
  await page.screenshot({
    path: testInfo.outputPath('wiki-security-safe.png'),
    fullPage: true,
  });
});

test('keeps the backend Content-Security-Policy unchanged', async ({ request }) => {
  const response = await request.get('/health');
  expect(response.status()).toBe(200);
  expect(response.headers()['content-security-policy']).toBe(
    "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https: blob:; connect-src 'self' ws: wss: http: https:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
  );
});

declare global {
  interface Window {
    __agkWikiXss?: boolean;
  }
}
