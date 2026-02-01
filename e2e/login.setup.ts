import { test as setup, expect } from '@playwright/test';
import { STORAGE_STATE } from '../playwright.config';
import assert from 'node:assert/strict';

assert(process.env.USERNAME1, 'USERNAME1 is not set');
assert(process.env.PASSWORD, 'PASSWORD is not set');

setup('Login', async ({ page }) => {
  setup.setTimeout(60_000);

  // Wait for the app to be fully interactive.
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeVisible({ timeout: 30_000 });

  // Use role-based locator for the sign-in link.
  await page.getByRole('link', { name: 'Sign in' }).click();

  await expect(page).toHaveURL(/\/user\/login/i, { timeout: 30_000 });
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeHidden({ timeout: 30_000 });

  await expect(page.getByRole('button', { name: 'Login' }))
    .toBeVisible({ timeout: 30_000 });

  await page.getByPlaceholder('Username').fill(process.env.USERNAME1);
  await page.getByPlaceholder('Password').fill(process.env.PASSWORD);
  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeVisible({ timeout: 30_000 });

  await page.context().storageState({ path: STORAGE_STATE });
});
