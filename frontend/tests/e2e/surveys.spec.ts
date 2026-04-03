import { test, expect } from '@playwright/test';

test.describe('Surveys Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/surveys');
  });

  test('surveys page loads correctly', async ({ page }) => {
    // Check page loads without error
    await expect(page.locator('body')).toBeVisible();
  });

  test('can navigate to surveys from home', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Surveys');
    await expect(page).toHaveURL(/\/surveys/);
  });
});
