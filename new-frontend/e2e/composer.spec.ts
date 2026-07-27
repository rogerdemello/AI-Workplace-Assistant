import { test, expect, Page } from "@playwright/test";

/** The composer must never lose a turn.
 *
 * A send issued while the previous reply is still in flight used to be dropped:
 * the input had already been cleared, no request went out, and nothing told the
 * employee. In a tool people use to raise things they would not raise
 * elsewhere, a message that disappears without an error is the worst failure
 * available — they have no reason to retry, and HR never learns there was
 * anything to hear. Sends during a reply are now queued.
 */

async function loginAs(page: Page, who: "Employee" | "HR") {
  await page.goto("/login");
  await page
    .getByRole("button", { name: new RegExp(who === "HR" ? "HR \\(hr1\\)" : "Employee \\(emp1\\)") })
    .click();
  await page.waitForURL(/\/(employee|dashboard|manager)/, { timeout: 15000 });
}

test("messages typed while a reply is in flight are not lost", async ({ page }) => {
  test.setTimeout(180_000);

  await loginAs(page, "Employee");
  await page.goto("/chat");

  const box = page.getByPlaceholder(/Tell MARK what's on your mind/i);
  await expect(box).toBeVisible({ timeout: 15000 });
  // Send is enabled only once the conversation exists. Before it does,
  // handleSend deliberately keeps the text in the box rather than swallowing
  // it — so wait for readiness, or we would be testing that guard instead.
  await box.fill("warmup");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({ timeout: 30_000 });
  await box.fill("");

  const stamp = Date.now();
  const first = `first probe ${stamp}`;
  const second = `second probe ${stamp}`;
  const third = `third probe ${stamp}`;

  // Fire three turns back to back with no wait between them. Before the queue,
  // everything after the first was swallowed.
  await box.fill(first);
  await box.press("Enter");
  await box.fill(second);
  await box.press("Enter");
  await box.fill(third);
  await box.press("Enter");

  for (const text of [first, second, third]) {
    await expect(page.getByText(text, { exact: false }).last()).toBeVisible({
      timeout: 90_000,
    });
  }
});

test("the composer clears only once a send is actually accepted", async ({ page }) => {
  await loginAs(page, "Employee");
  await page.goto("/chat");

  const box = page.getByPlaceholder(/Tell MARK what's on your mind/i);
  await expect(box).toBeVisible({ timeout: 15000 });
  // Send is enabled only once the conversation exists. Before it does,
  // handleSend deliberately keeps the text in the box rather than swallowing
  // it — so wait for readiness, or we would be testing that guard instead.
  await box.fill("warmup");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({ timeout: 30_000 });
  await box.fill("");

  const text = `clear probe ${Date.now()}`;
  await box.fill(text);
  await box.press("Enter");

  await expect(box).toHaveValue("", { timeout: 15_000 });
  await expect(page.getByText(text, { exact: false }).last()).toBeVisible({
    timeout: 60_000,
  });
});
