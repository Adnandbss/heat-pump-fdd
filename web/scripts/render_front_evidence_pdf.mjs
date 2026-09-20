import { chromium } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { marked } from "marked";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repo = resolve(webRoot, "..");
const docs = resolve(repo, "docs");
const mdPath = resolve(docs, "FRONT_EVIDENCE.md");
const htmlPath = resolve(docs, "FRONT_EVIDENCE.print.html");
const pdfPath = resolve(docs, "FRONT_EVIDENCE.pdf");

const raw = readFileSync(mdPath, "utf8");
const yamlMatch = raw.match(/^---\n([\s\S]*?)\n---\n/);
const meta = {};
if (yamlMatch) {
  for (const line of yamlMatch[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim().replace(/^"|"$/g, "");
  }
}
const bodyMd = yamlMatch ? raw.slice(yamlMatch[0].length) : raw;
const bodyHtml = marked.parse(bodyMd, { gfm: true });

const html = `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>${meta.title ?? "FRONT_EVIDENCE"}</title>
  <style>
    @page { size: A4; margin: 22mm 18mm 24mm 18mm; }
    html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body {
      font-family: Palatino, "Palatino Linotype", "Times New Roman", serif;
      font-size: 11pt;
      line-height: 1.45;
      color: #1a1a1a;
      max-width: 42rem;
      margin: 0 auto;
    }
    h1 { font-size: 18pt; margin: 1.6em 0 0.6em; page-break-after: avoid; }
    h2 { font-size: 14pt; margin: 1.4em 0 0.5em; page-break-after: avoid; }
    h3 { font-size: 12pt; margin: 1.2em 0 0.4em; page-break-after: avoid; }
    p, li { text-align: justify; hyphens: auto; }
    code { font-family: ui-monospace, Menlo, monospace; font-size: 0.86em; }
    pre {
      background: #f4f1ea;
      border: 1px solid #e0d8c8;
      padding: 0.8em 1em;
      overflow: hidden;
      font-size: 0.82em;
      page-break-inside: avoid;
    }
    table { border-collapse: collapse; width: 100%; font-size: 0.88em; margin: 0.8em 0 1.1em; page-break-inside: avoid; }
    th, td { border: 1px solid #d7d0c4; padding: 0.35em 0.5em; vertical-align: top; }
    th { background: #f4f1ea; text-align: left; }
    img { max-width: 100%; height: auto; display: block; margin: 0.6em 0 0.3em; border-radius: 6px; }
    em { color: #333; }
    .title { font-size: 22pt; margin: 0 0 0.3em; }
    .subtitle { font-size: 12pt; color: #444; margin: 0 0 0.2em; font-style: italic; }
    .date { font-size: 10pt; color: #666; margin-bottom: 2em; }
    hr { border: 0; border-top: 1px solid #d7d0c4; margin: 2em 0; }
  </style>
</head>
<body>
  <p class="title">${meta.title ?? ""}</p>
  <p class="subtitle">${meta.subtitle ?? ""}</p>
  <p class="date">${meta.date ?? ""}</p>
  ${bodyHtml}
</body>
</html>
`;

writeFileSync(htmlPath, html);
mkdirSync(docs, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
await page.pdf({
  path: pdfPath,
  format: "A4",
  printBackground: true,
  margin: { top: "18mm", bottom: "20mm", left: "16mm", right: "16mm" },
});
await browser.close();
console.log("wrote", pdfPath);
