import { test, expect } from '@playwright/test';

test.describe('Admin Users Page', () => {
  test('admin users route currently redirects to hr placeholder', async ({ page }) => {
    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/hr/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('admin users redirect does not crash on refresh', async ({ page }) => {
    await page.goto('/admin/users');
    await page.reload();
    await expect(page).toHaveURL(/\/hr/);
    await expect(page.locator('body')).toBeVisible();
  });
});
