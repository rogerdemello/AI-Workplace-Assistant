import { test, expect } from '@playwright/test';

test.describe('Email Draft Page', () => {
  test('email draft route redirects to employee workspace', async ({ page }) => {
    await page.goto('/email-draft');
    await expect(page).toHaveURL(/\/employee/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('email draft redirect is stable on refresh', async ({ page }) => {
    await page.goto('/email-draft');
    await page.reload();
    await expect(page).toHaveURL(/\/employee/);
    await expect(page.locator('body')).toBeVisible();
  });
});
