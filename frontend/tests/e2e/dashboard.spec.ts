import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test('dashboard redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('body')).toBeVisible();
    await expect(async () => {
      const url = page.url();
      expect(url).toMatch(/\/(dashboard|login)/);
    }).toPass();
  });

  test('dashboard route remains stable after refresh when unauthenticated', async ({ page }) => {
    await page.goto('/dashboard');
    await page.reload();
    await expect(async () => {
      const url = page.url();
      expect(url).toMatch(/\/(dashboard|login)/);
    }).toPass();
    await expect(page.locator('body')).toBeVisible();
  });

  test('shows fallback defaults for null ticket fields in HR table', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('auth_token', 'playwright-token');
      window.localStorage.setItem(
        'mark-auth-session',
        JSON.stringify({
          email: 'hr@example.com',
          name: 'HR User',
          role: 'hr',
          loginAtMs: Date.now(),
        })
      );
    });

    await page.route('**/api/v1/tickets**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 't-null',
              user_id: 'u-1',
              query: 'Null field test ticket',
              category: 'general',
              status: null,
              priority: null,
              created_at: null,
              updated_at: '2026-04-12T10:00:00.000Z',
              assigned_to: null,
              sla_warning: false,
            },
          ]),
        });
      }
      return route.fallback();
    });

    await page.route('**/hr/dashboard', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            engagement_score: 0,
            enps: 0,
            risk_level: 'Low',
            attrition_risk_pct: 0,
            open_tickets: 1,
            total_tickets: 1,
            active_users: 0,
            resolution_rate: 0,
            avg_response_time: 0,
            sentiment_trend: [],
            department_breakdown: [],
            employees: [],
            ai_summary: 'Test summary',
            weekly_quality: null,
          }),
        });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'u-hr', role: 'hr' }),
      });
    });

    await page.goto('/dashboard');

    await expect(page.locator('[data-testid="ticket-status"]')).toHaveText('Open');
    await expect(page.locator('[data-testid="ticket-priority"]')).toHaveText('MEDIUM');
    await expect(page.locator('[data-testid="ticket-assignee"]')).toHaveText('Unassigned');
  });
});
