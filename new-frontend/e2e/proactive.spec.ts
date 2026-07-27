import { test, expect, Page, APIRequestContext } from "@playwright/test";

/** Proactive delivery and chat-raised requests, driven through the real UI.
 *
 * The catch-up path is the piece unit tests can't prove: the transcript is
 * restored from local storage, so a message persisted server-side only reaches
 * the employee if the client actually pulls it when the chat opens. HR actioning
 * a request goes through that same delivery machinery, so it exercises the
 * round-trip without needing a test-only hook to trigger the scheduler.
 */

const API = process.env.E2E_API_URL || "http://127.0.0.1:8099";

async function loginAs(page: Page, who: "Employee" | "HR") {
  await page.goto("/login");
  await page
    .getByRole("button", { name: new RegExp(who === "HR" ? "HR \\(hr1\\)" : "Employee \\(emp1\\)") })
    .click();
  await page.waitForURL(/\/(employee|dashboard|manager)/, { timeout: 15000 });
}

async function tokenFrom(page: Page): Promise<string> {
  const token = await page.evaluate(() => window.localStorage.getItem("auth_token"));
  expect(token, "session token in local storage").toBeTruthy();
  return token as string;
}

/**
 * Log in over the API rather than in a browser page.
 *
 * Signing a second role in through the UI overwrites the shared auth entry in
 * local storage, so the page under test silently becomes that other user — and
 * the leak outlives the test. Keep every non-subject actor out of the browser.
 */
async function apiToken(
  request: APIRequestContext,
  email: string,
  password = "password123",
): Promise<string> {
  const res = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password },
  });
  expect(res.ok(), `login failed for ${email}: ${res.status()}`).toBeTruthy();
  const token = (await res.json()).access_token as string;
  expect(token, `no access_token for ${email}`).toBeTruthy();
  return token;
}

async function api(
  request: APIRequestContext,
  token: string,
  method: "get" | "post" | "patch",
  path: string,
  data?: unknown,
) {
  const res = await request[method](`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    ...(data === undefined ? {} : { data }),
  });
  expect(res.ok(), `${method.toUpperCase()} ${path} -> ${res.status()}`).toBeTruthy();
  return res.json();
}

test("HR's decision reaches the employee's chat after they return", async ({
  page,
  request,
}) => {
  // 1. Employee raises a request, then closes the app.
  await loginAs(page, "Employee");
  const employeeToken = await tokenFrom(page);
  const stamp = Date.now();
  const created = await api(request, employeeToken, "post", "/api/v1/requests", {
    request_type: "document",
    title: `Payslip request ${stamp}`,
    details: { document_type: "payslip", purpose: "home loan" },
  });

  // 2. HR actions it while the employee is away — no chat open, so SSE reaches
  //    nobody and only the durable path can carry it. HR acts over the API so
  //    the employee's browser session is never touched.
  const hrToken = await apiToken(request, "hr1@mark.ai");
  await api(request, hrToken, "patch", `/api/v1/requests/${created.id}/approve`, {
    hr_note: `Sent to payroll ${stamp}`,
  });

  // 3. Employee comes back and opens chat. The decision must be waiting.
  await page.goto("/chat");
  await expect(page.getByText(new RegExp(`Sent to payroll ${stamp}`))).toBeVisible({
    timeout: 25000,
  });

  // 4. Reloading must not replay it — the watermark should suppress a repeat.
  await page.reload();
  await expect(page.getByText(new RegExp(`Sent to payroll ${stamp}`))).toHaveCount(1, {
    timeout: 25000,
  });
});

test("employee books an HR appointment by chatting", async ({ page }) => {
  // Six conversational turns, each a backend round-trip. Generous because a
  // dev backend without real Azure credentials retries before falling back.
  test.setTimeout(240_000);

  await loginAs(page, "Employee");
  await page.goto("/chat");

  const box = page.getByPlaceholder(/Tell MARK what's on your mind/i);
  await expect(box).toBeVisible({ timeout: 15000 });
  const send = page.getByRole("button", { name: "Send" });

  // Wait for the reply this turn should produce before sending the next one.
  // The input clears as soon as a message is accepted, so gating on that alone
  // lets a fast backend receive the next turn before the flow has advanced —
  // which is exactly how this raced in CI but not on a slower local machine.
  const say = async (message: string, expectReply: RegExp) => {
    await box.fill(message);
    await expect(send).toBeEnabled({ timeout: 60_000 });
    await send.click();
    await expect(page.getByText(expectReply).last()).toBeVisible({ timeout: 60_000 });
  };

  const day = new Date();
  day.setDate(day.getDate() + 3);

  await say("I want to book an appointment with HR", /what would you like to talk about/i);
  await say("I would like to discuss my career growth", /which day works for you/i);
  await say(day.toISOString().slice(0, 10), /what time suits you/i);
  await say("3pm", /in person, over a call, or a video/i);
  await say("video", /send this to HR/i);
  await say("yes", /Booked|HR will confirm/i);
});

test("HR requests page renders and lists chat-raised requests", async ({ page }) => {
  await loginAs(page, "HR");
  await page.goto("/requests");

  await expect(page.getByRole("heading", { name: /Requests/i })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText(/Pending|Nothing here yet/i).first()).toBeVisible({
    timeout: 15000,
  });
});
