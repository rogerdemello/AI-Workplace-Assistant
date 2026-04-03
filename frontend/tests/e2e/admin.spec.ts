import { test, expect } from '@playwright/test';

test.describe('Admin Users Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/users');
  });

  test('admin page loads correctly', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
  });

  test('add user button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Add User")')).toBeVisible();
  });

  test('users table is displayed', async ({ page }) => {
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('th:has-text("Name")')).toBeVisible();
    await expect(page.locator('th:has-text("Email")')).toBeVisible();
    await expect(page.locator('th:has-text("Role")')).toBeVisible();
    await expect(page.locator('th:has-text("Department")')).toBeVisible();
    await expect(page.locator('th:has-text("Actions")')).toBeVisible();
  });

  test('sample users are displayed', async ({ page }) => {
    await expect(page.locator('text=John Doe')).toBeVisible();
    await expect(page.locator('text=jane@example.com')).toBeVisible();
    await expect(page.locator('text=admin@example.com')).toBeVisible();
  });

  test('can open add user modal', async ({ page }) => {
    await page.click('button:has-text("Add User")');
    await expect(page.locator('text=Add New User')).toBeVisible();
  });

  test('can close add user modal', async ({ page }) => {
    await page.click('button:has-text("Add User")');
    await expect(page.locator('text=Add New User')).toBeVisible();
    
    await page.click('button:has-text("Cancel")');
    await expect(page.locator('text=Add New User')).not.toBeVisible();
  });

  test('can search users', async ({ page }) => {
    const searchInput = page.locator('input[placeholder="Search users..."]');
    await searchInput.fill('john');
    
    await expect(page.locator('text=John Doe')).toBeVisible();
    await expect(page.locator('text=jane@example.com')).not.toBeVisible();
  });

  test('edit button opens modal', async ({ page }) => {
    await page.click('button:has-text("Edit")');
    await expect(page.locator('text=Edit User')).toBeVisible();
  });

  test('can delete user', async ({ page }) => {
    // Click delete button for John Doe
    await page.click('button:has-text("Delete")');
    
    // Confirm delete modal appears
    await expect(page.locator('text=Confirm Delete')).toBeVisible();
    
    // Confirm delete
    await page.click('button:has-text("Delete User")');
    
    // Check user is removed
    await expect(page.locator('text=John Doe')).not.toBeVisible();
  });
});
