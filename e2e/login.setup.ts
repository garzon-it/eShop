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

  // Assert the login route and the login form are ready.
  await expect(page).toHaveURL(/\/user\/login/i, { timeout: 30_000 });

  const username = page.getByPlaceholder('Username');
  const password = page.getByPlaceholder('Password');
  const loginButton = page.getByRole('button', { name: 'Login' });

  await expect(username).toBeVisible({ timeout: 30_000 });
  await expect(password).toBeVisible({ timeout: 30_000 });
  await expect(loginButton).toBeEnabled({ timeout: 30_000 });

  await username.fill(process.env.USERNAME1!);
  await password.fill(process.env.PASSWORD!);
  await loginButton.click();

  // Verify we're back on the home page (or post-login landing page).
  await expect(page.getByRole('heading', { name: 'Ready for a new adventure?' }))
    .toBeVisible({ timeout: 30_000 });

  await page.context().storageState({ path: STORAGE_STATE });
});
