import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('homepage loads correctly', async ({ page }) => {
    await expect(page).toHaveTitle(/HR Assistant/);
    await expect(page.locator('h1')).toContainText('HR Assistant');
  });

  test('can navigate to dashboard', async ({ page }) => {
    await page.click('text=Dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole('heading', { name: 'HR Analytics Dashboard' })).toBeVisible();
  });

  test('can navigate to tickets', async ({ page }) => {
    await page.click('text=Tickets');
    await expect(page).toHaveURL(/\/tickets/);
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
  });

  test('can navigate to email draft', async ({ page }) => {
    await page.click('text=Email Draft');
    await expect(page).toHaveURL(/\/email-draft/);
    await expect(page.getByRole('heading', { name: 'Email Draft Assistant' })).toBeVisible();
  });

  test('can navigate to surveys', async ({ page }) => {
    await page.click('text=Surveys');
    await expect(page).toHaveURL(/\/surveys/);
  });

  test('can navigate to admin', async ({ page }) => {
    await page.click('text=Admin');
    await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
  });

  test('navigation links are visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Home' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Tickets' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Email Draft' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Surveys' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Admin' })).toBeVisible();
  });
});
