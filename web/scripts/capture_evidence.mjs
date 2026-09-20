import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const out = resolve(root, "docs/front");
mkdirSync(out, { recursive: true });
const BASE = "http://127.0.0.1:5173";
const README = new Set(["00-full.png"]);
const SHOTS = [
  "01-hero.png",
  "02-ladder.png",
  "03-slope.png",
  "04-calibration.png",
  "05-references.png",
  "06-domain.png",
  "07-features.png",
  "08-rules.png",
  "09-perclass.png",
  "10-confusion.png",
  "11-runs.png",
  "00-full.png",
  "12-insights.png",
  "13-models.png",
];

function compressPng(path) {
  const oxipng = spawnSync("oxipng", ["-o4", "--strip", "safe", path], { encoding: "utf8" });
  if (oxipng.status === 0) return;
  const pngquant = spawnSync(
    "pngquant",
    ["--quality=70-90", "--speed", "1", "--ext", ".png", "--force", path],
    { encoding: "utf8" },
  );
  if (pngquant.status === 0) return;
  spawnSync(
    "python3",
    [
      "-c",
      "import sys; from PIL import Image; p=sys.argv[1]; im=Image.open(p); im.save(p, optimize=True)",
      path,
    ],
    { encoding: "utf8" },
  );
}

for (const name of readdirSync(out)) {
  if (name.endsWith(".png")) rmSync(resolve(out, name));
}

const browser = await chromium.launch({
  channel: process.env.PW_CHROME_CHANNEL || undefined,
});

async function openPage(dsf) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 920 },
    deviceScaleFactor: dsf,
  });
  const page = await context.newPage();
  await page.goto(`${BASE}/evidence`, { waitUntil: "networkidle", timeout: 60_000 });
  await page.waitForSelector("[data-testid='truth-ladder'] li", { timeout: 30_000 });
  await page.waitForTimeout(800);
  return { context, page };
}

const lite = await openPage(1);
await lite.page.screenshot({ path: resolve(out, "01-hero.png"), fullPage: false });
console.log("wrote 01-hero.png");

const figures = [
  ["truth-ladder", "02-ladder.png"],
  ["protocol-slope", "03-slope.png"],
  ["calibration-budget", "04-calibration.png"],
  ["reference-benchmark", "05-references.png"],
  ["domain-severity", "06-domain.png"],
  ["feature-contract", "07-features.png"],
  ["rules-bars", "08-rules.png"],
  ["per-class-bars", "09-perclass.png"],
  ["confusion-heatmap", "10-confusion.png"],
  ["runs-table", "11-runs.png"],
];
for (const [testId, name] of figures) {
  await lite.page.locator(`[data-testid='${testId}']`).screenshot({ path: resolve(out, name) });
  console.log("wrote", name);
}

await lite.page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await lite.page.waitForTimeout(800);
await lite.page.screenshot({ path: resolve(out, "12-insights.png"), fullPage: false });
console.log("wrote 12-insights.png");

await lite.page.goto(`${BASE}/models`, { waitUntil: "networkidle" });
await lite.page.waitForTimeout(1000);
await lite.page.screenshot({ path: resolve(out, "13-models.png"), fullPage: false });
console.log("wrote 13-models.png");
await lite.context.close();

const hero = await openPage(2);
await hero.page.screenshot({ path: resolve(out, "00-full.png"), fullPage: true });
console.log("wrote 00-full.png");
await hero.context.close();
await browser.close();

let bytes = 0;
for (const name of SHOTS) {
  const path = resolve(out, name);
  compressPng(path);
  bytes += statSync(path).size;
  console.log("compressed", name, `${(statSync(path).size / 1024).toFixed(0)} KiB`);
}
console.log(`docs/front total ${(bytes / 1024 / 1024).toFixed(2)} Mo`);
if (bytes > 2 * 1024 * 1024) {
  console.warn("docs/front is above the 2 Mo target");
}

void README;
