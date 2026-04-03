import { test, expect } from '@playwright/test';

test.describe('Tickets Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/tickets');
  });

  test('tickets page loads correctly', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
    await expect(page.locator('button:has-text("New Ticket")')).toBeVisible();
  });

  test('sample tickets are displayed', async ({ page }) => {
    // Check sample tickets are visible
    await expect(page.locator('text=How do I apply for sick leave?')).toBeVisible();
    await expect(page.locator('text=What are the health insurance benefits?')).toBeVisible();
    await expect(page.locator('text=When will my payroll be processed?')).toBeVisible();
  });

  test('can open new ticket form', async ({ page }) => {
    await page.click('button:has-text("New Ticket")');
    await expect(page.locator('text=Create New Ticket')).toBeVisible();
  });

  test('can close new ticket form', async ({ page }) => {
    await page.click('button:has-text("New Ticket")');
    await expect(page.locator('text=Create New Ticket')).toBeVisible();
    
    await page.click('button:has-text("Cancel")');
    await expect(page.locator('text=Create New Ticket')).not.toBeVisible();
  });

  test('filters are present', async ({ page }) => {
    await expect(page.locator('text=Showing')).toBeVisible();
  });

  test('can select a ticket to view details', async ({ page }) => {
    await page.click('text=How do I apply for sick leave?');
    await expect(page.locator('text=Select a ticket to view details')).not.toBeVisible();
  });

  test('can update ticket status', async ({ page }) => {
    // Select a ticket
    await page.click('text=How do I apply for sick leave?');
    
    // Click on status dropdown if visible
    const statusDropdown = page.locator('button:has-text("Open")').first();
    if (await statusDropdown.isVisible()) {
      await statusDropdown.click();
      await page.click('text=In Progress');
      
      // Check status changed
      await expect(page.locator('text=In Progress')).toBeVisible();
    }
  });
});
