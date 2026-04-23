import { test, expect } from '@playwright/test';

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat');
  });

  test('chat page loads', async ({ page }) => {
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('Chat Greeting Deduplication', () => {
  test('reload does not duplicate chat greeting', async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.reload();

    await page.fill('#login-email', 'employee@mark.ai');
    await page.fill('#login-password', 'password123');
    await page.click('#login-submit');

    await page.waitForURL('/employee', { timeout: 10000 });

    const openButton = page.locator('button[aria-label="Open Mark assistant"]');
    await expect(openButton).toBeVisible({ timeout: 5000 });
    await openButton.click();

    await page.waitForTimeout(1000);

    const greetingCount = async () =>
      page.locator('div.rounded-2xl.rounded-tl-sm:has-text("I\'m Mark")').count();

    const countBeforeReload = await greetingCount();
    expect(countBeforeReload).toBe(1);

    await page.reload();
    await page.waitForURL('/employee', { timeout: 10000 });

    await expect(openButton).toBeVisible({ timeout: 5000 });
    await openButton.click();

    await page.waitForTimeout(500);

    const countAfterReload = await greetingCount();
    expect(countAfterReload).toBe(1);
  });
});