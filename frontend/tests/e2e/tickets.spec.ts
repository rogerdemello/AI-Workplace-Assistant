import { expect, test, type Page, type Route } from '@playwright/test';

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function seedAuth(page: Page) {
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
}

async function mockTicketApis(page: Page) {
  const context = page.context();

  const tickets = [
    {
      id: 't-1',
      user_id: 'u-1',
      query: 'How do I apply for sick leave?',
      category: 'leave',
      status: 'open',
      priority: 'medium',
      created_at: '2026-04-12T10:00:00.000Z',
      updated_at: '2026-04-12T10:00:00.000Z',
      sla_warning: false,
    },
    {
      id: 't-2',
      user_id: 'u-1',
      query: 'Payroll deduction mismatch this month',
      category: 'payroll',
      status: 'escalated',
      priority: 'high',
      created_at: '2026-04-11T09:00:00.000Z',
      updated_at: '2026-04-11T09:00:00.000Z',
      sla_warning: true,
      sla_due_at: '2026-04-14T09:00:00.000Z',
    },
    {
      id: 't-null',
      user_id: 'u-1',
      query: 'Null field test ticket',
      category: 'general',
      status: null,
      priority: null,
      created_at: null,
      updated_at: '2026-04-12T10:00:00.000Z',
      sla_warning: false,
    },
  ];

  const messageByTicket: Record<string, Array<{ id: string; ticket_id: string; sender_id: string | null; message_text: string; created_at: string }>> = {
    't-1': [],
    't-2': [],
  };

  await context.route('**/api/v1/**', async (route) => {
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS',
          'access-control-allow-headers': '*',
        },
      });
    }
    return route.fallback();
  });

  await context.route('**/api/v1/auth/me', async (route) => {
    return json(route, { id: 'u-1', role: 'employee' });
  });

  await context.route('**/api/v1/tickets/*/messages', async (route) => {
    const url = new URL(route.request().url());
    const parts = url.pathname.split('/');
    const ticketId = parts[parts.length - 2];

    if (route.request().method() === 'GET') {
      return json(route, messageByTicket[ticketId] ?? []);
    }

    if (route.request().method() === 'POST') {
      const payload = JSON.parse(route.request().postData() ?? '{}') as { message_text?: string };
      const message = {
        id: `m-${Date.now()}`,
        ticket_id: ticketId,
        sender_id: 'u-1',
        message_text: payload.message_text ?? '',
        created_at: new Date().toISOString(),
      };
      messageByTicket[ticketId] = [...(messageByTicket[ticketId] ?? []), message];
      return json(route, message, 200);
    }

    return route.fallback();
  });

  await context.route('**/api/v1/tickets/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/messages')) {
      return route.fallback();
    }
    const ticketId = url.pathname.split('/').pop() ?? '';

    if (route.request().method() === 'PATCH') {
      const updates = JSON.parse(route.request().postData() ?? '{}') as { status?: string; priority?: string };
      const index = tickets.findIndex((t) => t.id === ticketId);
      if (index === -1) return json(route, { detail: 'Ticket not found' }, 404);

      tickets[index] = {
        ...tickets[index],
        ...(updates.status ? { status: updates.status } : {}),
        ...(updates.priority ? { priority: updates.priority } : {}),
        updated_at: new Date().toISOString(),
      };
      return json(route, tickets[index]);
    }

    return route.fallback();
  });

  await context.route('**/api/v1/tickets**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.includes('/messages')) {
      return route.fallback();
    }

    if (request.method() === 'GET') {
      return json(route, tickets);
    }

    if (request.method() === 'POST') {
      const payload = JSON.parse(request.postData() ?? '{}') as { query: string; category: string; priority?: string };
      const created = {
        id: `t-${Date.now()}`,
        user_id: 'u-1',
        query: payload.query,
        category: payload.category,
        status: 'open',
        priority: payload.priority ?? 'medium',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        sla_warning: false,
      };
      tickets.unshift(created);
      return json(route, created, 200);
    }

    return route.fallback();
  });
}

test.describe('Tickets Page', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
    await mockTicketApis(page);
    await page.goto('/tickets');
  });

  test('loads page and lists tickets from API', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Support Tickets' })).toBeVisible();
    await expect(page.locator('text=How do I apply for sick leave?')).toBeVisible();
    await expect(page.locator('text=Payroll deduction mismatch this month')).toBeVisible();
  });

  test('opens ticket detail panel', async ({ page }) => {
    await page.getByText('How do I apply for sick leave?').first().click();
    await expect(page.getByText('Ticket Details')).toBeVisible();
    await expect(page.getByText('Ticket ID')).toBeVisible();
  });

  test('posts and shows ticket conversation comments', async ({ page }) => {
    await page.click('text=How do I apply for sick leave?');
    await expect(page.locator('text=Ticket Conversation')).toBeVisible();

    await page.fill('#ticket-comment', 'Adding more context for HR follow-up.');
    await page.click('button:has-text("Post comment")');

    await expect(page.locator('text=Adding more context for HR follow-up.')).toBeVisible();
  });

  test('shows fallback defaults for null ticket fields in detail panel', async ({ page }) => {
    await page.getByText('Null field test ticket').first().click();
    const detail = page.locator('[data-testid="ticket-detail"]');
    await expect(detail.locator('[data-testid="ticket-status"]')).toHaveText('Open');
    await expect(detail.locator('[data-testid="ticket-priority"]')).toHaveText('Medium');
    await expect(detail.locator('[data-testid="ticket-created-at"]')).toHaveText('—');
  });
});
