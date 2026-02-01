import { test as setup, expect } from '@playwright/test';
import { STORAGE_STATE } from '../playwright.config';
import { assert } from 'console';

assert(process.env.USERNAME1, 'USERNAME1 is not set');
assert(process.env.PASSWORD, 'PASSWORD is not set');

setup('Login', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' })).toBeVisible();

  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => null),
    page.getByRole('link', { name: 'Sign in' }).click(),
  ]);

  console.log('After sign-in URL:', page.url());

  try {
    await expect(page.getByPlaceholder('Username')).toBeVisible({ timeout: 30_000 });
  } catch (e) {
    console.log('FAIL URL:', page.url());
    await page.screenshot({ path: 'login-failure.png', fullPage: true });
    throw e;
  }


  await page.getByPlaceholder('Username').fill(process.env.USERNAME1!);
  await page.getByPlaceholder('Password').fill(process.env.PASSWORD!);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' })).toBeVisible();
  await page.context().storageState({ path: STORAGE_STATE });
})
