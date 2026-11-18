/* ui_test.js — 浏览器实测：渲染、控制台错误、交互
 *
 * 用 puppeteer-core 驱动本机 Chrome。没有 puppeteer 时降级为提示。
 * 这是「机器质检」，不等于艺术验收——构图与叙事仍需人眼。
 *
 *   node tools/ui_test.js
 *   node tools/ui_test.js http://localhost:5200
 */
"use strict";

const path = require("path");
const fs = require("fs");
const { execSync } = require("child_process");

function findChrome() {
  const cands = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    path.join(process.env.LOCALAPPDATA || "", "Google\\Chrome\\Application\\chrome.exe"),
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  for (const c of cands) if (fs.existsSync(c)) return c;
  return null;
}

let puppeteer;
try {
  puppeteer = require("puppeteer-core");
} catch (e) {
  try {
    puppeteer = require(path.join(__dirname, "pptr", "node_modules", "puppeteer-core"));
  } catch (e2) {
    console.log("缺少 puppeteer-core，跳过浏览器测试。");
    console.log("安装：npm i puppeteer-core");
    process.exit(0);
  }
}

const BASE = process.argv[2] || "http://localhost:5200";
const OUT = path.join(__dirname, "..", "docs");

const CASES = [
  { q: "水", name: "zh-water", desc: "中文单字：义项+音标" },
  { q: "学生", name: "zh-student", desc: "中文词：繁体标注" },
  { q: "美丽", name: "zh-beautiful", desc: "形容词：音标对齐" },
  { q: "livre", name: "fr-livre", desc: "法语词反向查" },
  { q: "maison", name: "fr-maison", desc: "法语词多义" },
];

(async () => {
  const chrome = findChrome();
  if (!chrome) {
    console.log("找不到 Chrome/Edge，跳过。");
    process.exit(0);
  }

  const browser = await puppeteer.launch({
    executablePath: chrome,
    headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--force-device-scale-factor=2"],
  });

  let fail = 0;
  const report = [];

  async function checkPage(view, viewport, label) {
    const page = await browser.newPage();
    await page.setViewport(viewport);

    const errors = [];
    page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", e => errors.push(String(e)));

    for (const c of CASES) {
      await page.goto(`${BASE}/?q=${encodeURIComponent(c.q)}&view=${view}`,
        { waitUntil: "networkidle2", timeout: 45000 });
      await new Promise(r => setTimeout(r, 700));

      const info = await page.evaluate(() => {
        const hero = document.querySelector(".hero, .card");
        // 中文结果用 .sense（义项行），法语结果用 .answer（主译）+ .fam-row（词族）
        const senses = document.querySelectorAll(".sense, .det-sense, .answer").length;
        const ipas = document.querySelectorAll(".ipa").length;
        const pending = document.querySelectorAll(".ipa.pending").length;
        const lias = document.querySelectorAll(".lia-item").length;
        return {
          hasHero: !!hero,
          heroText: hero ? hero.textContent.slice(0, 60) : "",
          senses, ipas, pending, lias,
          bodyW: document.body.scrollWidth,
          winW: window.innerWidth,
          count: (document.getElementById("count") || {}).textContent || "",
        };
      });

      const overflow = info.bodyW > info.winW + 2;
      const ok = info.hasHero && info.senses > 0 && !overflow;
      if (!ok) fail++;

      report.push({
        label, view, q: c.q,
        ok, overflow,
        senses: info.senses,
        ipas: info.ipas,
        pending: info.pending,
        lias: info.lias,
        hero: info.heroText,
      });

      // 截图
      const dir = path.join(OUT, "screenshots");
      fs.mkdirSync(dir, { recursive: true });
      await page.screenshot({
        path: path.join(dir, `${label}-${c.name}.png`),
        fullPage: false,
      });
    }

    if (errors.length) {
      fail++;
      console.log(`✗ ${label} 控制台错误 ${errors.length} 条：`);
      errors.slice(0, 5).forEach(e => console.log("   " + e.slice(0, 160)));
    } else {
      console.log(`✓ ${label} 控制台 0 错误`);
    }

    await page.close();
  }

  await checkPage("dict", { width: 390, height: 844 }, "mobile");
  await checkPage("dict", { width: 1280, height: 900 }, "desktop");

  await browser.close();

  console.log("\n结果：");
  for (const r of report) {
    const flag = r.ok ? "✓" : "✗";
    console.log(`${flag} ${r.label}/${r.q}  义项 ${r.senses}  音标 ${r.ipas}（待核 ${r.pending}）  联诵 ${r.lias}` +
      (r.overflow ? "  ← 横向溢出！" : ""));
  }

  fs.writeFileSync(path.join(OUT, "ui_test_report.json"),
    JSON.stringify(report, null, 2), "utf8");

  console.log("");
  if (fail) {
    console.log(`失败 ${fail} 项`);
    process.exit(1);
  }
  console.log("全部通过。截图在 docs/screenshots/");
})();