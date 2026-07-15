#!/usr/bin/env node
/*
 * SUZAKU サイト全ページ監査(常設)
 *
 * 使い方:
 *   python3 -m http.server 8930   # リポジトリルートで配信
 *   node scripts/audit.js         # 別シェルで実行
 *
 * 環境変数:
 *   AUDIT_BASE    配信URL(既定 http://localhost:8930)
 *   AUDIT_WIDTH   ビューポート幅(既定 375 = モバイル。1440でPC検査)
 *   AUDIT_LIMIT   検査ページ数の上限(デバッグ用)
 *
 * 検査項目(1つでも検出すると終了コード1):
 *   - HTTP 200 以外 / ナビゲーション失敗
 *   - コンソールエラー / pageerror(フォントCDN遮断由来のノイズは除外)
 *   - 横スクロール(本文のはみ出し)
 *   - 壊れ画像(complete かつ naturalWidth === 0)
 *   - ページ内リンクの 404(サイト内・重複除去して全数HEAD検査)
 */
const fs = require("fs");
const path = require("path");

function requirePlaywright() {
  const candidates = [
    "playwright",
    "/opt/node22/lib/node_modules/playwright",
    "/opt/homebrew/lib/node_modules/playwright",
    "/usr/local/lib/node_modules/playwright"
  ];
  for (const mod of candidates) {
    try { return require(mod); } catch {}
  }
  console.error(
    "Playwright が見つかりません。全ページ監査を実行するには `npm i -D playwright` " +
    "または `npm i -g playwright` を実行してから、再度 `node scripts/audit.js` を実行してください。"
  );
  process.exit(2);
}

const ROOT = path.join(__dirname, "..");
const BASE = process.env.AUDIT_BASE || "http://localhost:8930";
const WIDTH = parseInt(process.env.AUDIT_WIDTH || "375", 10);
const LIMIT = parseInt(process.env.AUDIT_LIMIT || "0", 10);

// 対象URL: ファイルシステム上の全 index.html(noindexページも含む)
function collectPages() {
  const urls = [];
  (function walk(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.name.startsWith(".") || ["node_modules", "scripts", "src", "docs"].includes(e.name)) continue;
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name === "index.html") {
        urls.push("/" + path.relative(ROOT, dir).split(path.sep).join("/") + "/");
      }
    }
  })(ROOT);
  if (fs.existsSync(path.join(ROOT, "index.html"))) urls.push("/");
  return [...new Set(urls)].sort().map((u) => (u === "/./" ? "/" : u));
}

(async () => {
  const { chromium } = requirePlaywright();
  const exe = fs.existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined;
  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 820 } });
  await ctx.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());

  let pages = collectPages();
  if (LIMIT > 0) pages = pages.slice(0, LIMIT);
  const issues = [];
  const seenLinks = new Set();
  const linkStatus = new Map();

  console.log(`監査開始: ${pages.length}ページ / ${BASE} / 幅${WIDTH}px`);
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.accept().catch(() => {}));
  let current = "";
  const noise = /fonts\.(googleapis|gstatic)|net::ERR_FAILED|ERR_CONNECTION_RESET|favicon/;
  page.on("console", (m) => {
    if (m.type() === "error" && !noise.test(m.text())) issues.push(`${current} console: ${m.text().slice(0, 200)}`);
  });
  page.on("pageerror", (e) => issues.push(`${current} pageerror: ${String(e.message).slice(0, 200)}`));

  for (const u of pages) {
    current = u;
    let resp;
    try {
      resp = await page.goto(BASE + u, { waitUntil: "domcontentloaded", timeout: 20000 });
    } catch (e) {
      issues.push(`${u} nav失敗: ${e.message.split("\n")[0]}`);
      continue;
    }
    if (resp && resp.status() !== 200) issues.push(`${u} HTTP ${resp.status()}`);
    await page.waitForTimeout(350);
    const r = await page.evaluate(() => {
      const broken = [...document.images]
        .filter((i) => i.complete && i.naturalWidth === 0 && !/fonts\./.test(i.src))
        .map((i) => i.getAttribute("src"));
      const hscroll = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
      const links = [...document.querySelectorAll("a[href^='/']")]
        .map((a) => a.getAttribute("href").split("#")[0])
        .filter((h) => h && !h.startsWith("//"));
      return { broken, hscroll, links };
    });
    for (const b of r.broken) issues.push(`${u} 壊れ画像: ${b}`);
    if (r.hscroll) issues.push(`${u} 横スクロール発生`);
    for (const l of r.links) seenLinks.add(l);
  }

  // サイト内リンクの実在検査(重複除去してHEAD)
  for (const l of [...seenLinks]) {
    const clean = l.split("?")[0];
    if (linkStatus.has(clean)) continue;
    try {
      const res = await page.request.fetch(BASE + clean, { method: "HEAD", timeout: 10000 });
      linkStatus.set(clean, res.status());
      if (res.status() >= 400) issues.push(`リンク切れ(${res.status()}): ${clean}`);
    } catch (e) {
      issues.push(`リンク検査失敗: ${clean}`);
    }
  }

  await browser.close();
  console.log(`検査リンク数: ${linkStatus.size}`);
  if (issues.length) {
    console.log(`\nNG ${issues.length}件:`);
    for (const i of issues) console.log(" - " + i);
    process.exit(1);
  }
  console.log("問題 0件: OK");
})();
