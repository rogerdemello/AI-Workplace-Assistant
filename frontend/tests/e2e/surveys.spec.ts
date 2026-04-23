import { test, expect } from '@playwright/test';

test.describe('Surveys Page', () => {
  test('surveys route redirects to hr placeholder', async ({ page }) => {
    await page.goto('/surveys');
    await expect(page).toHaveURL(/\/hr/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('surveys redirect is stable after refresh', async ({ page }) => {
    await page.goto('/surveys');
    await page.reload();
    await expect(page).toHaveURL(/\/hr/);
    await expect(page.locator('body')).toBeVisible();
  });
});
