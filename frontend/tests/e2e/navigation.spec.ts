import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('homepage loads correctly', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
    await expect(async () => {
      const url = page.url();
      expect(url).toMatch(/\/($|login|employee|dashboard|tickets)/);
    }).toPass();
  });

  test('dashboard route is reachable', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(async () => {
      const url = page.url();
      expect(url).toMatch(/\/(dashboard|login)/);
    }).toPass();
  });

  test('tickets page is reachable directly', async ({ page }) => {
    await page.goto('/tickets');
    await expect(page).toHaveURL(/\/tickets/);
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
  });

  test('email draft route redirects to employee workspace', async ({ page }) => {
    await page.goto('/email-draft');
    await expect(page).toHaveURL(/\/employee/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('surveys route redirects to hr placeholder', async ({ page }) => {
    await page.goto('/surveys');
    await expect(page).toHaveURL(/\/hr/);
  });

  test('admin users route redirects to hr placeholder', async ({ page }) => {
    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/hr/);
  });

  test('login page content is visible', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Sign in to Mark' })).toBeVisible();
  });

  test('employee route redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/employee');
    await expect(page).toHaveURL(/\/login/);
  });

  test('chat page can load', async ({ page }) => {
    await page.goto('/chat');
    await expect(async () => {
      const url = page.url();
      expect(url).toMatch(/\/(chat|login|employee)/);
    }).toPass();
    await expect(page.locator('body')).toBeVisible();
  });
});
