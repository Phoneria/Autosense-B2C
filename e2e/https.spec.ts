import { test, expect } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('production HTTPS proxy, SMTP verification, secure session and real analysis', async ({ page, context, browser }) => {
  const email = `https-${Date.now()}@example.com`;
  const password = 'Copper!Garden-94-Drive';
  mkdirSync('.local/screenshots', { recursive: true });
  await page.goto('/login');
  await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeEnabled();
  await page.screenshot({ path: '.local/screenshots/login-https-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Hesap oluşturun' }).click();
  await page.getByLabel('E-posta', { exact: true }).fill(email);
  await page.getByLabel('Parola', { exact: true }).fill(password);
  await page.getByLabel('Parola tekrar', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Hesap oluştur' }).click();
  await expect(page).toHaveURL(/\/verify-email$/);

  let messageId = '';
  await expect.poll(async () => {
    const response = await page.request.get('http://localhost:8026/api/v1/messages');
    expect(response.ok()).toBe(true);
    const messages = await response.json();
    messageId = messages.messages.find((message: { To: { Address: string }[] }) => message.To.some(to => to.Address === email))?.ID || '';
    return messageId;
  }, { message: 'The configured SMTP server must receive the verification email' }).not.toBe('');
  const message = await (await page.request.get(`http://localhost:8026/api/v1/message/${messageId}`)).json();
  const code = message.Text.match(/^\s*(\d{6})\s*$/m)?.[1];
  expect(code).toBeTruthy();
  await page.getByLabel('Doğrulama kodu', { exact: true }).fill(code!);
  await page.getByRole('button', { name: 'E-postamı doğrula' }).click();
  // The code completes the pending login, so verification lands inside the app.
  await expect(page.getByRole('heading', { name: 'Araç ve ilan bilgileri' })).toBeVisible();
  expect((await page.request.get('/api/b2c/me')).status()).toBe(200);
  await page.getByRole('button', { name: /Çıkış/ }).click();
  // Logging out of the protected route lands on /login?next=%2F.
  await expect(page).toHaveURL(/\/login(\?|$)/);
  await page.getByLabel('E-posta', { exact: true }).fill(email);
  await page.getByLabel('Parola', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Giriş yap' }).click();
  await expect(page.getByRole('heading', { name: 'Araç ve ilan bilgileri' })).toBeVisible();
  const cookies = await context.cookies();
  for (const name of ['b2c_sessionid', 'b2c_csrftoken']) {
    expect(cookies.find(cookie => cookie.name === name)).toMatchObject({ secure: true, httpOnly: true, sameSite: 'Lax' });
  }
  const me = await page.request.get('/api/b2c/me');
  expect(me.headers()['cache-control']).toContain('no-store');
  await page.reload();
  await page.getByLabel(/^Marka/).selectOption({ label: 'Fiat' });
  await page.getByLabel(/^Seri/).selectOption({ label: 'Egea' });
  await page.getByLabel(/^Motor/).selectOption({ label: '1.3 Multijet' });
  await page.getByLabel(/^Paket/).selectOption({ label: 'Easy' });
  await page.getByLabel('Model yılı', { exact: true }).fill('2023');
  await page.getByLabel('Kilometre').fill('100000');
  await page.getByLabel('İlan fiyatı').fill('1200000');
  const analyzing = page.waitForResponse(response => response.url().endsWith('/api/b2c/analyze') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analizi başlat' }).click();
  const result = await analyzing;
  expect(result.status(), await result.text()).toBe(200);
  expect((await result.json()).estimate.tahmini_fiyat).toBeGreaterThan(0);
  await expect(page.getByRole('heading', { name: 'Analiz sonucu', exact: true })).toBeVisible();
  await page.screenshot({ path: '.local/screenshots/analysis-https-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '.local/screenshots/analysis-https-mobile.png', fullPage: true });
  const state = await context.storageState();
  await page.getByRole('button', { name: /Çıkış/ }).click();
  await expect(page).toHaveURL(/\/login/);
  const oldSession = await browser.newContext({ storageState: state, baseURL: 'https://localhost:8443', ignoreHTTPSErrors: true });
  expect((await oldSession.request.get('/api/b2c/me')).status()).toBe(401);
  await oldSession.close();
});
