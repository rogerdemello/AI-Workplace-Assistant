import { test, expect } from '@playwright/test';

test.describe('Employee Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('auth_token', 'playwright-token');
      window.localStorage.setItem(
        'mark-auth-session',
        JSON.stringify({
          email: 'employee@example.com',
          name: 'Employee User',
          role: 'employee',
          loginAtMs: Date.now(),
        })
      );
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'u-emp', role: 'employee' }),
      });
    });
  });

  test('all 4 widget containers are visible with real API data', async ({ page }) => {
    await page.route('**/api/v1/tickets**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 't-1',
              user_id: 'u-emp',
              query: 'My laptop is broken and I need a replacement urgently',
              category: 'it',
              status: 'open',
              priority: 'high',
              assigned_to: null,
              created_at: '2026-04-20T10:00:00.000Z',
              updated_at: '2026-04-20T10:00:00.000Z',
              sla_warning: false,
            },
            {
              id: 't-2',
              user_id: 'u-emp',
              query: 'Requesting access to the new project folder',
              category: 'access',
              status: 'in_progress',
              priority: 'medium',
              assigned_to: 'u-hr',
              created_at: '2026-04-21T09:00:00.000Z',
              updated_at: '2026-04-21T09:00:00.000Z',
              sla_warning: false,
            },
          ]),
        });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/leave**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 'l-1',
              employee_id: 'u-emp',
              employee_name: 'Employee User',
              leave_type: 'annual_leave',
              start_date: '2026-05-01',
              end_date: '2026-05-05',
              reason: 'Family vacation',
              status: 'pending',
              created_at: '2026-04-15T08:00:00.000Z',
            },
          ]),
        });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/wellbeing/reminders**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 'r-1',
              reminder_type: 'wellness',
              title: 'Stretch break',
              message: 'Take a 5-minute stretch break',
              schedule_kind: 'daily',
              run_at: null,
              cron_expr: null,
              timezone: 'UTC',
              status: 'active',
              next_trigger_at: '2026-04-23T15:00:00.000Z',
              last_triggered_at: null,
              created_at: '2026-04-01T00:00:00.000Z',
            },
          ]),
        });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/wellbeing/weekly-summary**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            window_days: 7,
            high_risk_employees: 0,
            followup_signals: 2,
            open_tickets: 2,
            avg_engagement_score: 72,
            top_issues: [{ category: 'workload', count: 1 }],
          }),
        });
      }
      return route.fallback();
    });

    await page.goto('/employee');

    await expect(page.getByTestId('my-tickets-widget')).toBeVisible();
    await expect(page.getByTestId('my-leaves-widget')).toBeVisible();
    await expect(page.getByTestId('my-reminders-widget')).toBeVisible();
    await expect(page.getByTestId('mood-snapshot-widget')).toBeVisible();

    const ticketsWidget = page.getByTestId('my-tickets-widget');
    await expect(ticketsWidget.locator('text=My laptop is broken')).toBeVisible();
    await expect(ticketsWidget.locator('text=open')).toBeVisible();
    await expect(ticketsWidget.locator('text=high')).toBeVisible();

    const leavesWidget = page.getByTestId('my-leaves-widget');
    await expect(leavesWidget.locator('text=annual leave')).toBeVisible();
    await expect(leavesWidget.locator('text=pending')).toBeVisible();

    const remindersWidget = page.getByTestId('my-reminders-widget');
    await expect(remindersWidget.getByText('Stretch break', { exact: true })).toBeVisible();

    const moodWidget = page.getByTestId('mood-snapshot-widget');
    await expect(moodWidget.locator('text=72%')).toBeVisible();
  });

  test('shows empty states when API returns no data', async ({ page }) => {
    await page.route('**/api/v1/tickets**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/leave**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/wellbeing/reminders**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 404 });
      }
      return route.fallback();
    });

    await page.route('**/api/v1/wellbeing/weekly-summary**', async (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 500 });
      }
      return route.fallback();
    });

    await page.goto('/employee');

    await expect(page.getByTestId('my-tickets-widget')).toBeVisible();
    await expect(page.getByTestId('my-leaves-widget')).toBeVisible();
    await expect(page.getByTestId('my-reminders-widget')).toBeVisible();
    await expect(page.getByTestId('mood-snapshot-widget')).toBeVisible();

    await expect(page.getByTestId('my-tickets-widget').locator('text=No tickets yet')).toBeVisible();
    await expect(page.getByTestId('my-leaves-widget').locator('text=No leave requests')).toBeVisible();
    await expect(page.getByTestId('my-reminders-widget').locator('text=Reminders appear here')).toBeVisible();
    await expect(page.getByTestId('mood-snapshot-widget').locator('text=No mood data available')).toBeVisible();
  });
});
