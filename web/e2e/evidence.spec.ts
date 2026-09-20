import { expect, test } from "@playwright/test";

test("evidence page renders six figures without NaN", async ({ page }) => {
  await page.goto("/evidence");
  await expect(page.getByTestId("truth-ladder")).toBeVisible();
  await expect(page.getByTestId("protocol-slope")).toBeVisible();
  await expect(page.getByTestId("reference-benchmark")).toBeVisible();
  await expect(page.getByTestId("per-class-bars")).toBeVisible();
  await expect(page.getByTestId("confusion-heatmap")).toBeVisible();
  await expect(page.getByTestId("runs-table")).toBeVisible();
  await expect(page.getByTestId("truth-ladder").locator("li").first()).toBeVisible({ timeout: 30_000 });
  const body = await page.locator("main").innerText();
  expect(body).not.toMatch(/\bNaN\b/);
  expect(body).not.toMatch(/\bundefined\b/);
});
