import { test, expect } from '@playwright/test';

test.describe('Email Draft Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/email-draft');
  });

  test('email draft page loads correctly', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Email Draft Assistant' })).toBeVisible();
  });

  test('compose email form is visible', async ({ page }) => {
    await expect(page.locator('text=Compose Email')).toBeVisible();
    await expect(page.locator('text=Select the type and tone')).toBeVisible();
  });

  test('form elements are present', async ({ page }) => {
    await expect(page.getByText('Email Type', { exact: true })).toBeVisible();
  });

  test('tone buttons are present', async ({ page }) => {
    await expect(page.locator('button:has-text("Formal")')).toBeVisible();
  });

  test('context textarea is visible', async ({ page }) => {
    const contextTextarea = page.locator('textarea[id="context"]');
    await expect(contextTextarea).toBeVisible();
  });

  test('generate button is disabled without required fields', async ({ page }) => {
    const generateButton = page.locator('button:has-text("Generate Draft")');
    await expect(generateButton).toBeDisabled();
  });

  test('generate button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Generate Draft")')).toBeVisible();
  });

  test('context textarea works', async ({ page }) => {
    const contextTextarea = page.locator('textarea[id="context"]');
    await contextTextarea.fill('Test context');
    await expect(contextTextarea).toHaveValue('Test context');
  });
});
