import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { mkdirSync } from 'node:fs';

const password = 'Violet!Harbor-72-Road';
const newPassword = 'Amber!Forest-83-Wheel';
const root = process.cwd();

async function emailValue(email: string, route: string): Promise<string> {
  let result = '';
  await expect.poll(() => {
    try {
      result = execFileSync(path.join(root, '.venv/bin/python'), ['e2e/mail_link.py', email, route], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      return result;
    } catch { return ''; }
  }, { message: 'The actual MIME email must contain a working frontend link or code' }).not.toBe('');
  return result;
}

async function login(page: Page, email: string, value = password) {
  await page.goto('/login');
  await page.getByLabel('E-posta', { exact: true }).fill(email);
  await page.getByLabel('Parola', { exact: true }).fill(value);
  await page.getByRole('button', { name: 'Giriş yap' }).click();
  await expect(page.getByRole('heading', { name: 'Araç ve ilan bilgileri' })).toBeVisible();
}

async function register(page: Page, email: string) {
  await page.goto('/signup');
  await page.getByLabel('E-posta', { exact: true }).fill(email);
  await page.getByLabel('Parola', { exact: true }).fill(password);
  await page.getByLabel('Parola tekrar', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Hesap oluştur' }).click();
  await expect(page).toHaveURL(/\/verify-email$/);
  const code = await emailValue(email, 'code');
  await page.getByLabel('Doğrulama kodu', { exact: true }).fill(code);
  await page.getByRole('button', { name: 'E-postamı doğrula' }).click();
  // The code is entered by the session that signed up, so it also completes the login.
  await expect(page.getByRole('heading', { name: 'Araç ve ilan bilgileri' })).toBeVisible();
  expect((await page.request.get('/api/b2c/me')).status()).toBe(200);
  await page.getByRole('button', { name: /Çıkış/ }).click();
  // Logging out of the protected route lands on /login?next=%2F.
  await expect(page).toHaveURL(/\/login(\?|$)/);
  return code;
}

async function noHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test('real email registration, verified login, persisted analysis, logout and password reset', async ({ page, context, browser }) => {
  const email = `journey-${Date.now()}@example.com`;
  const browserErrors: string[] = [];
  page.on('pageerror', error => browserErrors.push(error.message));
  mkdirSync(path.join(root, '.local/screenshots'), { recursive: true });
  await page.goto('/login');
  await expect(page.getByRole('button', { name: 'Giriş yap' })).toBeEnabled();
  await page.screenshot({ path: '.local/screenshots/login-desktop.png', fullPage: true });
  const verifyCode = await register(page, email);
  await login(page, email);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const cookies = await context.cookies();
  expect(cookies.find(cookie => cookie.name === 'b2c_sessionid')).toMatchObject({ httpOnly: true, sameSite: 'Lax' });
  expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({});
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Araç ve ilan bilgileri' })).toBeVisible();

  await page.getByLabel(/^Marka/).selectOption({ label: 'Fiat' });
  await page.getByLabel(/^Seri/).selectOption({ label: 'Egea' });
  await page.getByLabel(/^Motor/).selectOption({ label: '1.3 Multijet' });
  await page.getByLabel('Paket', { exact: false }).selectOption({ label: 'Easy' });
  await page.getByLabel('Model yılı', { exact: true }).fill('2023');
  await page.getByLabel('Kilometre').fill('100000');
  await page.getByLabel('İlan fiyatı').fill('1200000');
  const analysis = page.waitForResponse(response => response.url().endsWith('/api/b2c/analyze') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analizi başlat' }).click();
  const response = await analysis;
  expect(response.status(), await response.text()).toBe(200);
  const result = await response.json();
  expect(result.estimate.tahmini_fiyat).toBeGreaterThan(0);
  await expect(page.getByRole('heading', { name: 'Analiz sonucu', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pazarlık planı', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Kaput,/ }).click();
  await page.getByRole('button', { name: /^Kaput,/ }).click();
  await page.getByRole('button', { name: /^Kaput,/ }).click();
  await expect(page.getByRole('button', { name: /^Kaput, Değişen/ })).toBeVisible();
  const changedAnalysis = page.waitForResponse(response => response.url().endsWith('/api/b2c/analyze') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Analizi başlat' }).click();
  const changedResponse = await changedAnalysis;
  expect(changedResponse.request().postDataJSON().damage).toContainEqual({ parca: 'Kaput', durum: 'Değişmiş' });
  expect(changedResponse.status(), await changedResponse.text()).toBe(200);
  expect((await changedResponse.json()).estimate.tahmini_fiyat).toBeGreaterThan(0);
  await expect(page.getByRole('heading', { name: 'Analiz sonucu', exact: true })).toBeVisible();
  await page.screenshot({ path: '.local/screenshots/analysis-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await noHorizontalOverflow(page);
  await page.screenshot({ path: '.local/screenshots/analysis-mobile.png', fullPage: true });
  const loggedInState = await context.storageState();
  await page.getByRole('button', { name: /Çıkış/ }).click();
  await expect(page).toHaveURL(/\/login/);
  const revoked = await browser.newContext({ storageState: loggedInState, baseURL: 'http://127.0.0.1:5176' });
  expect((await revoked.request.get('/api/b2c/me')).status()).toBe(401);
  await revoked.close();

  await login(page, email);
  const preResetState = await context.storageState();
  await page.goto('/forgot-password');
  await page.getByLabel('E-posta', { exact: true }).fill(email);
  await page.getByRole('button', { name: 'Sıfırlama bağlantısı gönder' }).click();
  await expect(page.getByRole('status')).toContainText('bir hesap varsa');
  const resetLink = await emailValue(email, 'reset-password');
  await page.goto(resetLink);
  await page.getByLabel('Yeni parola', { exact: true }).fill(newPassword);
  await page.getByLabel('Yeni parola tekrar', { exact: true }).fill(newPassword);
  await page.getByRole('button', { name: 'Parolayı kaydet' }).click();
  await expect(page.getByRole('heading', { name: 'Parolanız yenilendi.' })).toBeVisible();
  const oldSession = await browser.newContext({ storageState: preResetState, baseURL: 'http://127.0.0.1:5176' });
  expect((await oldSession.request.get('/api/b2c/me')).status()).toBe(401);
  await oldSession.close();
  await login(page, email, newPassword);
  await page.getByRole('button', { name: /Çıkış/ }).click();
  await page.goto(resetLink);
  await page.getByLabel('Yeni parola', { exact: true }).fill(password);
  await page.getByLabel('Yeni parola tekrar', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Parolayı kaydet' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  // A spent code must not verify a second time, and the process is gone with it.
  await page.goto('/verify-email');
  await page.getByLabel('Doğrulama kodu', { exact: true }).fill(verifyCode);
  await page.getByRole('button', { name: 'E-postamı doğrula' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test('unauthenticated redirects, invalid links and mobile labels', async ({ page }) => {
  const businessRequests: string[] = [];
  page.on('request', request => {
    if (/\/api\/(arabam-vehicles|b2c\/(vehicles|locations|analyze|vehicle-defaults|lookup-text))/.test(request.url())) businessRequests.push(request.url());
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByLabel('E-posta', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Parola', { exact: true })).toHaveAttribute('autocomplete', 'current-password');
  await noHorizontalOverflow(page);
  expect(businessRequests).toEqual([]);
  await page.goto('/verify-email');
  await page.getByLabel('Doğrulama kodu', { exact: true }).fill('000000');
  await page.getByRole('button', { name: 'E-postamı doğrula' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await noHorizontalOverflow(page);
  await page.goto('/reset-password/not-a-valid-key');
  await page.getByLabel('Yeni parola', { exact: true }).fill(password);
  await page.getByLabel('Yeni parola tekrar', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Parolayı kaydet' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await noHorizontalOverflow(page);
});

test('server-side session expiry returns the loaded application to login', async ({ page }) => {
  const email = `expiry-${Date.now()}@example.com`;
  await register(page, email);
  await login(page, email);
  // Expire real server sessions while preserving browser cookies and mounted React state.
  execFileSync(path.join(root, '.venv/bin/python'), ['-c', 'import sqlite3; db=sqlite3.connect(".local/e2e/accounts.sqlite3"); db.execute("UPDATE django_session SET expire_date = ?", ("2000-01-01 00:00:00",)); db.commit()'], { cwd: root });
  await page.getByLabel(/^Marka/).selectOption({ label: 'Fiat' });
  await page.getByLabel(/^Seri/).selectOption({ label: 'Egea' });
  await page.getByLabel(/^Motor/).selectOption({ label: '1.3 Multijet' });
  await expect(page).toHaveURL(/\/login/);
  expect((await page.request.get('/api/b2c/me')).status()).toBe(401);
});
