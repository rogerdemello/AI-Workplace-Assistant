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

  test('form validation works', async ({ page }) => {
    await page.goto('/admin/users');
    
    // Try to submit empty form
    await page.click('button:has-text("Add User")');
    await page.click('button:has-text("Create User")');
    
    // Form should still be visible (validation prevented submission)
    await expect(page.locator('text=Add New User')).toBeVisible();
  });

  test('handles rapid navigation', async ({ page }) => {
    await page.goto('/');
    
    // Rapidly navigate between pages
    await page.click('text=Dashboard');
    await page.click('text=Tickets');
    await page.click('text=Email Draft');
    await page.click('text=Admin');
    await page.click('text=Home');
    
    // Should end up on home page
    await expect(page).toHaveURL('/');
  });

  test('handles page refresh', async ({ page }) => {
    await page.goto('/tickets');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
  });

  test('handles back/forward navigation', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Dashboard');
    await page.click('text=Tickets');
    
    // Go back
    await page.goBack();
    await expect(page).toHaveURL(/\/dashboard/);
    
    // Go forward
    await page.goForward();
    await expect(page).toHaveURL(/\/tickets/);
  });

  test('UI elements remain responsive', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'HR Analytics Dashboard' })).toBeVisible();
  });

  test('handles page navigation', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('search handles special characters', async ({ page }) => {
    await page.goto('/admin/users');
    
    const searchInput = page.locator('input[placeholder="Search users..."]');
    
    // Try special characters
    await searchInput.fill("' OR '1'='1");
    await searchInput.fill('<>script</script>');
    await searchInput.fill('');
    
    // Should not crash and show results
    await expect(page.locator('table')).toBeVisible();
  });
});
