import { expect, test } from "@playwright/test";

test("fleet triage lists units and routes unvalidated faults to review", async ({ page }) => {
  await page.goto("/fleet");
  await expect(page.getByTestId("fleet-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("fleet-row").first()).toBeVisible();
  expect(await page.getByTestId("fleet-row").count()).toBeGreaterThan(0);
  await expect(page.locator('[data-testid="action-pill"][data-action="engineering_review"]').first()).toBeVisible();

  const dispatched = page.locator('[data-testid="fleet-row"]', {
    has: page.locator('[data-action="dispatch"]'),
  });
  const count = await dispatched.count();
  for (let i = 0; i < count; i += 1) {
    await expect(dispatched.nth(i).getByTestId("evidence-badge")).toHaveAttribute("data-status", "transfers");
  }

  const body = await page.locator("main").innerText();
  expect(body).not.toMatch(/\bNaN\b/);
  expect(body).not.toMatch(/\bundefined\b/);
});
