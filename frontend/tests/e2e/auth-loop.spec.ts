import { test, expect } from '@playwright/test';

test.describe('Auth Loop Fix', () => {
  test('spinner disappears within 3 seconds on dashboard', async ({ page }) => {
    await page.goto('/dashboard');

    await expect(
      page.locator('text=Verifying authentication...')
    ).not.toBeVisible({ timeout: 3500 });

    await expect(page.locator('body')).toBeVisible();
    const url = page.url();
    expect(url).toMatch(/\/(dashboard|login)/);
  });

  test('reload does not re-trigger infinite spinner', async ({ page }) => {
    await page.goto('/dashboard');

    await expect(
      page.locator('text=Verifying authentication...')
    ).not.toBeVisible({ timeout: 3500 });

    await page.reload();

    await expect(
      page.locator('text=Verifying authentication...')
    ).not.toBeVisible({ timeout: 3500 });

    const url = page.url();
    expect(url).toMatch(/\/(dashboard|login)/);
  });
});
