import { expect, test } from "@playwright/test";

test("evidence page renders figures without NaN", async ({ page }) => {
  await page.goto("/evidence");
  await expect(page.getByTestId("truth-ladder")).toBeVisible();
  await expect(page.getByTestId("protocol-slope")).toBeVisible();
  await expect(page.getByTestId("calibration-budget")).toBeVisible();
  await expect(page.getByTestId("reference-benchmark")).toBeVisible();
  await expect(page.getByTestId("domain-severity")).toBeVisible();
  await expect(page.getByTestId("feature-contract")).toBeVisible();
  await expect(page.getByTestId("rules-bars")).toBeVisible();
  await expect(page.getByTestId("per-class-bars")).toBeVisible();
  await expect(page.getByTestId("confusion-heatmap")).toBeVisible();
  await expect(page.getByTestId("runs-table")).toBeVisible();
  await expect(page.getByTestId("truth-ladder").locator("li").first()).toBeVisible({ timeout: 30_000 });
  const body = await page.locator("main").innerText();
  expect(body).not.toMatch(/\bNaN\b/);
  expect(body).not.toMatch(/\bundefined\b/);
});

test("tabbing through Evidence shows a visible focus ring", async ({ page }) => {
  await page.goto("/evidence");
  await expect(page.getByTestId("truth-ladder")).toBeVisible();
  await page.locator("body").click({ position: { x: 4, y: 4 } });
  let visibleStops = 0;
  for (let i = 0; i < 16; i += 1) {
    await page.keyboard.press("Tab");
    const visible = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body || el === document.documentElement) return false;
      const shadow = getComputedStyle(el).boxShadow;
      return Boolean(shadow && shadow !== "none" && !shadow.startsWith("none"));
    });
    if (visible) visibleStops += 1;
  }
  expect(visibleStops).toBeGreaterThan(0);
});
