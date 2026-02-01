import { test as setup, expect } from '@playwright/test';
import { STORAGE_STATE } from '../playwright.config';
import { assert } from 'console';

assert(process.env.USERNAME1, 'USERNAME1 is not set');
assert(process.env.PASSWORD, 'PASSWORD is not set');

setup('Login', async ({ page }) => {
  setup.setTimeout(60_000);

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeVisible({ timeout: 30_000 });

  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => null),
    page.getByRole('link', { name: 'Sign in' }).click(),
  ]);

  console.log('After sign-in URL:', page.url());
  console.log('Title:', await page.title());

  try {
    await expect(page.getByPlaceholder('Username')).toBeVisible({ timeout: 30_000 });
  } catch (e) {
    console.log('FAIL URL:', page.url());
    console.log('Body snippet:', (await page.textContent('body'))?.slice(0, 300));
    try {
      await page.screenshot({ path: 'test-results/login-failure.png', fullPage: true });
    } catch (err) {
      console.log('Screenshot failed (page likely closed):', String(err));
    }
    throw e;
  }

  await page.getByPlaceholder('Username').fill(process.env.USERNAME1!);
  await page.getByPlaceholder('Password').fill(process.env.PASSWORD!);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeVisible({ timeout: 30_000 });

  await page.context().storageState({ path: STORAGE_STATE });
});
