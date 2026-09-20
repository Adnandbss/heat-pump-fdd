import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const out = resolve(root, "docs/front");
mkdirSync(out, { recursive: true });

const BASE = "http://[::1]:5173";
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 920 },
  deviceScaleFactor: 2,
});

async function shot(name) {
  await page.screenshot({ path: resolve(out, name), fullPage: false });
  console.log("wrote", name);
}

await page.goto(`${BASE}/evidence`, { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForSelector("[data-testid='truth-ladder'] li", { timeout: 30_000 });
await page.waitForTimeout(800);

await shot("01-hero.png");
await page.locator("[data-testid='truth-ladder']").screenshot({ path: resolve(out, "02-ladder.png") });
console.log("wrote 02-ladder.png");
await page.locator("[data-testid='protocol-slope']").screenshot({ path: resolve(out, "03-slope.png") });
console.log("wrote 03-slope.png");
await page.locator("[data-testid='reference-benchmark']").screenshot({ path: resolve(out, "04-references.png") });
console.log("wrote 04-references.png");
await page.locator("[data-testid='per-class-bars']").screenshot({ path: resolve(out, "05-perclass.png") });
console.log("wrote 05-perclass.png");
await page.locator("[data-testid='confusion-heatmap']").screenshot({ path: resolve(out, "06-confusion.png") });
console.log("wrote 06-confusion.png");
await page.locator("[data-testid='runs-table']").screenshot({ path: resolve(out, "07-runs.png") });
console.log("wrote 07-runs.png");
await page.screenshot({ path: resolve(out, "00-full.png"), fullPage: true });
console.log("wrote 00-full.png");

await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await shot("08-insights.png");

await page.goto(`${BASE}/models`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
await shot("09-models.png");

await browser.close();
