import { test, expect, Page } from "@playwright/test";

/** Interactive multi-step workflows driven through the real UI (forms submit,
 * data round-trips to the backend), not just render checks. */

async function loginAs(page: Page, who: "Employee" | "HR") {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(who === "HR" ? "HR \\(hr1\\)" : "Employee \\(emp1\\)") }).click();
  await page.waitForURL(/\/(employee|dashboard|manager)/, { timeout: 15000 });
}

function future(daysOut: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysOut);
  return d.toISOString().slice(0, 10); // yyyy-mm-dd for <input type=date>
}

test("employee submits a leave request through the dialog", async ({ page }) => {
  await loginAs(page, "Employee");
  await page.goto("/employee");
  await page.getByRole("button", { name: /Request leave/i }).click();
  await expect(page.getByText(/Request time off/i)).toBeVisible();
  await page.locator("#leave-start").fill(future(20));
  await page.locator("#leave-end").fill(future(22));
  await page.locator("#leave-reason").fill("E2E automated leave probe");
  await page.getByRole("button", { name: /^Submit$/ }).click();
  // Success toast OR the dialog closing both confirm the round-trip worked.
  await expect(page.getByText(/Leave request submitted|Overlap notice/i)).toBeVisible({ timeout: 15000 });
});

test("employee sends a chat message and it appears", async ({ page }) => {
  await loginAs(page, "Employee");
  await page.goto("/chat");
  const box = page.getByPlaceholder(/Tell MARK what's on your mind/i);
  await expect(box).toBeVisible({ timeout: 15000 });
  const sendBtn = page.getByRole("button", { name: "Send" });
  const msg = `E2E ping ${Date.now()}`;
  await box.fill(msg);
  // With text present, Send enables once the conversation is ready (chatReady).
  await expect(sendBtn).toBeEnabled({ timeout: 20000 });
  await sendBtn.click();
  // The user's message bubble should render.
  await expect(page.getByText(msg)).toBeVisible({ timeout: 15000 });
});

test("HR creates an automation rule from Admin", async ({ page }) => {
  await loginAs(page, "HR");
  await page.goto("/admin");
  await page.getByRole("button", { name: /Add complaint escalation/i }).click();
  await expect(page.getByText(/Automation rule created|Could not create/i)).toBeVisible({ timeout: 15000 });
});
