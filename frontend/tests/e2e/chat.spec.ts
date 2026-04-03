import { test, expect } from '@playwright/test';

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat');
  });

  test('chat page loads', async ({ page }) => {
    await expect(page.locator('body')).toBeVisible();
  });
});
