import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('dashboard page loads correctly', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'HR Analytics Dashboard' })).toBeVisible();
  });

  test('KPI cards are displayed', async ({ page }) => {
    await expect(page.locator('text=Engagement Score')).toBeVisible();
    await expect(page.locator('text=Resolution Rate')).toBeVisible();
    await expect(page.locator('text=Avg Response')).toBeVisible();
    await expect(page.locator('text=Active Users')).toBeVisible();
  });

  test('charts are displayed', async ({ page }) => {
    await expect(page.locator('text=Sentiment Trend')).toBeVisible();
    await expect(page.locator('text=Resolution by Priority')).toBeVisible();
  });

  test('page content loads', async ({ page }) => {
    await expect(page.locator('body')).toBeVisible();
  });

  test('charts are rendered', async ({ page }) => {
    await expect(page.locator('text=Sentiment Trend')).toBeVisible();
    await expect(page.locator('text=Resolution by Priority')).toBeVisible();
  });
});
