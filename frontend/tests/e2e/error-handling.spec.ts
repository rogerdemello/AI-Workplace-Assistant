import { test, expect } from '@playwright/test';

test.describe('Error Handling', () => {
  test('handles 404 gracefully', async ({ page }) => {
    // Navigate to non-existent route
    await page.goto('/nonexistent-page');
    
    // Should either show 404 or redirect
    // The app should not crash
    const body = await page.locator('body');
    await expect(body).toBeVisible();
  });

  test('chat page loads', async ({ page }) => {
    await page.goto('/chat');
    await expect(page.locator('body')).toBeVisible();
  });

  test('handles rapid navigation', async ({ page }) => {
    await page.goto('/tickets');
    await page.goto('/dashboard');
    await page.goto('/login');
    await expect(page.locator('body')).toBeVisible();
  });

  test('handles page refresh', async ({ page }) => {
    await page.goto('/tickets');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
  });

  test('handles back/forward navigation', async ({ page }) => {
    await page.goto('/tickets');
    await page.goto('/login');
    
    // Go back
    await page.goBack();
    await expect(page).toHaveURL(/\/tickets/);
    
    // Go forward
    await page.goForward();
    await expect(page).toHaveURL(/\/login/);
  });

  test('UI elements remain responsive', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Sign in to Mark' })).toBeVisible();
  });

  test('handles page navigation', async ({ page }) => {
    await page.goto('/');
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login/);
  });
});
