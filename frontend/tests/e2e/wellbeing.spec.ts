import { test, expect, type Page, type Route } from '@playwright/test';

type UserRole = 'employee' | 'hr';

function seedSession(page: Page, role: UserRole) {
  const email = role === 'hr' ? 'hr@example.com' : 'employee@example.com';
  const name = role === 'hr' ? 'HR User' : 'Employee User';
  return page.addInitScript(
    ({ seededEmail, seededName, seededRole }) => {
      window.localStorage.setItem(
        'mark-auth-session',
        JSON.stringify({
          email: seededEmail,
          name: seededName,
          role: seededRole,
          loginAtMs: Date.now(),
        })
      );
      window.localStorage.setItem('auth_token', 'playwright-token');
    },
    { seededEmail: email, seededName: name, seededRole: role }
  );
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockEmployeeWellbeingApis(page: Page) {
  let reminders: Array<{
    id: string;
    reminder_type: string;
    title: string;
    message: string;
    schedule_kind: string;
    run_at: string | null;
    cron_expr: string | null;
    timezone: string;
    status: 'active';
    next_trigger_at: string | null;
    last_triggered_at: string | null;
    created_at: string;
  }> = [];

  await page.route('**/api/v1/leave**', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, []);
    }
    return route.fallback();
  });

  await page.route('**/api/chat/memory-cards', async (route) => {
    return json(route, { cards: [] });
  });

  await page.route('**/api/v1/wellbeing/check-ins/daily', async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fallback();
    }
    return json(route, {
      mood: 'okay',
      signal: {
        triage_level: 'watch',
      },
      suggested_next_step: 'Thanks for checking in. Keep taking short breaks.',
    }, 201);
  });

  await page.route('**/api/v1/wellbeing/reminders**', async (route) => {
    const method = route.request().method();
    if (method === 'GET') {
      return json(route, reminders);
    }
    if (method === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}') as {
        reminder_type?: string;
        title?: string;
        message?: string;
        schedule_kind?: string;
        run_at?: string;
      };
      const created = {
        id: `r-${Date.now()}`,
        reminder_type: body.reminder_type || 'custom',
        title: body.title || 'Reminder',
        message: body.message || 'Message',
        schedule_kind: body.schedule_kind || 'one_time',
        run_at: body.run_at || null,
        cron_expr: null,
        timezone: 'UTC',
        status: 'active' as const,
        next_trigger_at: body.run_at || null,
        last_triggered_at: null,
        created_at: new Date().toISOString(),
      };
      reminders = [created, ...reminders];
      return json(route, created, 201);
    }
    return route.fallback();
  });

  await page.route('**/api/v1/wellbeing/reminders/*', async (route) => {
    const method = route.request().method();
    const url = new URL(route.request().url());
    const reminderId = url.pathname.split('/').pop() || '';

    if (method === 'PATCH') {
      const updates = JSON.parse(route.request().postData() || '{}') as { status?: 'active' | 'paused' | 'cancelled' };
      reminders = reminders.map((r) => (r.id === reminderId ? { ...r, status: (updates.status || r.status) as 'active' } : r));
      const updated = reminders.find((r) => r.id === reminderId);
      return json(route, updated || reminders[0]);
    }

    if (method === 'DELETE') {
      reminders = reminders.filter((r) => r.id !== reminderId);
      return route.fulfill({ status: 204, body: '' });
    }

    return route.fallback();
  });
}

async function mockHrDashboardApis(page: Page) {
  await page.route('**/api/v1/auth/me', async (route) => {
    return json(route, { id: 'hr-user', role: 'hr' });
  });

  await page.route('**/hr/dashboard', async (route) => {
    return json(route, {
      engagement_score: 72,
      enps: 24,
      risk_level: 'Medium',
      attrition_risk_pct: 38,
      open_tickets: 9,
      total_tickets: 24,
      active_users: 18,
      resolution_rate: 0.61,
      avg_response_time: 3.1,
      sentiment_trend: [
        { date: '2026-04-10', positive: 52, neutral: 30, negative: 18 },
        { date: '2026-04-11', positive: 56, neutral: 28, negative: 16 },
      ],
      department_breakdown: [
        { department: 'Engineering', positive: 54, neutral: 26, negative: 20, score: 34, total_messages: 40 },
      ],
      employees: [
        {
          id: 'e1',
          employee_id: 'EMP001',
          name: 'Asha Sharma',
          sentiment_score: 58,
          risk_score: 62,
          last_active: '2 hours ago',
          department: 'Engineering',
        },
      ],
      ai_summary: 'Summary from mocked dashboard API.',
      weekly_quality: {
        window_days: 7,
        feedback_responses: 8,
        avg_csat: 4.3,
        helpful_rate: 82.4,
        detractor_rate: 5.2,
        avg_first_response_seconds: 9.8,
        conversations_measured: 13,
        quality_label: 'Good',
      },
    });
  });

  await page.route('**/api/v1/analytics/dashboard**', async (route) => {
    return json(route, {
      metrics: {
        engagement_score: 72,
        resolution_rate: 0.61,
        avg_response_time: 3.1,
        active_users: 18,
        total_tickets: 24,
        open_tickets: 9,
      },
      sentiment: [
        { date: '2026-04-10', positive: 52, neutral: 30, negative: 18 },
        { date: '2026-04-11', positive: 56, neutral: 28, negative: 16 },
      ],
      employees: [
        {
          id: 'e1',
          employee_id: 'EMP001',
          name: 'Asha Sharma',
          sentiment_score: 58,
          risk_score: 62,
          last_active: '2 hours ago',
          department: 'Engineering',
        },
      ],
      weekly_quality: {
        window_days: 7,
        feedback_responses: 8,
        avg_csat: 4.3,
        helpful_rate: 82.4,
        detractor_rate: 5.2,
        avg_first_response_seconds: 9.8,
        conversations_measured: 13,
        quality_label: 'Good',
      },
      ai_summary: 'Summary from mocked dashboard API.',
    });
  });

  await page.route('**/api/v1/tickets**', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, [
        {
          id: 't1',
          user_id: 'u1',
          query: 'Manager is assigning unfair weekend tasks',
          category: 'Manager X',
          status: 'open',
          priority: 'high',
          created_at: '2026-04-10T10:00:00.000Z',
          updated_at: '2026-04-10T10:00:00.000Z',
          sla_warning: true,
          sla_due_at: '2026-04-12T10:00:00.000Z',
        },
        {
          id: 't2',
          user_id: 'u2',
          query: 'Escalating concerns about manager behavior',
          category: 'Manager X',
          status: 'in_progress',
          priority: 'high',
          created_at: '2026-04-11T10:00:00.000Z',
          updated_at: '2026-04-11T10:00:00.000Z',
          sla_warning: false,
          sla_due_at: '2026-04-15T10:00:00.000Z',
        },
        {
          id: 't3',
          user_id: 'u3',
          query: 'Complaint about repetitive pressure from manager',
          category: 'Manager X',
          status: 'escalated',
          priority: 'critical',
          created_at: '2026-04-12T10:00:00.000Z',
          updated_at: '2026-04-12T10:00:00.000Z',
          sla_warning: true,
          sla_due_at: '2026-04-13T10:00:00.000Z',
        },
      ]);
    }
    return route.fallback();
  });

  await page.route('**/api/v1/leave**', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, []);
    }
    return route.fallback();
  });

  await page.route('**/api/v1/wellbeing/weekly-summary', async (route) => {
    return json(route, {
      window_days: 7,
      high_risk_employees: 2,
      followup_signals: 4,
      open_tickets: 9,
      avg_engagement_score: 71.5,
      top_issues: [{ category: 'manager_conflict', count: 3 }],
    });
  });

  await page.route('**/api/v1/wellbeing/high-risk**', async (route) => {
    return json(route, [
      {
        user_id: 'u-1',
        name: 'Rohan Iyer',
        mood_score: 34,
        risk_score: 82,
        risk_level: 'high',
        open_tickets: 2,
        last_active: '1 day ago',
        reasons: ['High burnout indicators from recent conversations'],
      },
    ]);
  });

  await page.route('**/api/v1/alerts**', async (route) => {
    return json(route, []);
  });
}

test.describe('Wellbeing flows', () => {
  test('employee daily check-in is inferred from chat', async ({ page }) => {
    await seedSession(page, 'employee');
    await mockEmployeeWellbeingApis(page);

    await page.goto('/employee');
    await expect(page.getByRole('heading', { name: 'Daily Check-In (Automatic)' })).toBeVisible();

    await page.getByLabel('Open Mark assistant').click();
    const chatInput = page.getByPlaceholder('Reply to Mark...');
    await chatInput.fill('I feel overwhelmed today and pretty stressed.');
    await chatInput.press('Enter');

    await expect(page.getByTestId('toast-success')).toContainText('Check-in inferred');
  });

  test('employee reminder is inferred from chat', async ({ page }) => {
    await seedSession(page, 'employee');
    await mockEmployeeWellbeingApis(page);

    await page.goto('/employee');
    await expect(page.getByRole('heading', { name: 'Reminders (Automatic)' })).toBeVisible();

    await page.getByLabel('Open Mark assistant').click();
    const chatInput = page.getByPlaceholder('Reply to Mark...');
    await chatInput.fill('Remind me to take medicine tomorrow at 9 AM');
    await chatInput.press('Enter');

    await expect(page.getByTestId('toast-success')).toContainText('Reminder inferred');
  });

  test('HR dashboard shows wellbeing intelligence from API', async ({ page }) => {
    await seedSession(page, 'hr');
    await mockHrDashboardApis(page);

    await page.goto('/dashboard');

    await expect(page.getByRole('heading', { name: 'Wellbeing intelligence' })).toBeVisible();
    await expect(page.locator('text=7 days')).toBeVisible();
    await expect(page.locator('text=Rohan Iyer')).toBeVisible();
    await expect(page.locator('text=High burnout indicators from recent conversations')).toBeVisible();
  });

  test('HR dashboard surfaces grouped ticket insight card', async ({ page }) => {
    await seedSession(page, 'hr');
    await mockHrDashboardApis(page);

    await page.goto('/dashboard');

    await expect(page.getByText('Multiple complaints about Manager X (3 tickets).')).toBeVisible();
  });
});
