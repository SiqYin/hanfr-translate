/* shot_theme.js — 深色主题 + 四语言截图验证
 *
 *   node tools/shot_theme.js
 */
"use strict";

const path = require("path");
const fs = require("fs");

function findChrome() {
  const c = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    path.join(process.env.LOCALAPPDATA || "", "Google\\Chrome\\Application\\chrome.exe"),
  ];
  for (const x of c) if (fs.existsSync(x)) return x;
  return null;
}

let puppeteer;
try { puppeteer = require("puppeteer-core"); } catch (e) {
  console.log("缺 puppeteer-core"); process.exit(0);
}

const BASE = process.argv[2] || "http://localhost:5200";
const OUT = path.join(__dirname, "..", "docs", "screenshots");

(async () => {
  const chrome = findChrome();
  if (!chrome) { console.log("无 Chrome"); process.exit(0); }
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: chrome, headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--force-device-scale-factor=2"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844 });

  const errors = [];
  page.on("pageerror", e => errors.push(String(e)));
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });

  // 1) 深色主题
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem("hanfr.ui.theme", "dark");
  });
  await page.goto(`${BASE}/?q=水`, { waitUntil: "networkidle2" });
  await new Promise(r => setTimeout(r, 700));
  await page.screenshot({ path: path.join(OUT, "dark-zh-water.png") });
  console.log("✓ dark-zh-water.png");

  // 2) 四语言
  const langs = [
    ["hant", "學生", "lang-hant"],
    ["fr", "maison", "lang-fr"],
    ["en", "livre", "lang-en"],
  ];
  for (const [lang, q, name] of langs) {
    await page.evaluate((l) => {
      localStorage.setItem("hanfr.ui.lang", l);
      localStorage.setItem("hanfr.ui.theme", "light");
    }, lang);
    await page.goto(`${BASE}/?q=${encodeURIComponent(q)}`, { waitUntil: "networkidle2" });
    await new Promise(r => setTimeout(r, 700));
    await page.screenshot({ path: path.join(OUT, `${name}.png`) });
    const title = await page.$eval(".brand h1", el => el.textContent);
    console.log(`✓ ${name}.png  标题="${title}"`);
  }

  // 3) 翻译页
  await page.evaluate(() => {
    localStorage.setItem("hanfr.ui.lang", "hans");
    localStorage.setItem("hanfr.ui.theme", "light");
  });
  await page.goto(`${BASE}/?view=ai`, { waitUntil: "networkidle2" });
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: path.join(OUT, "ai-page.png") });
  console.log("✓ ai-page.png");

  // 4) 例句 + 联诵：找一个有例句的词
  const withEx = await page.evaluate(() => {
    for (let i = 0; i < (window.ZF || []).length; i++) {
      const e = window.ZF[i];
      if (e[6] && e[6][1] && e[6][3] && e[6][3].length) {
        return { zh: e[1], n: e[6][3].length };
      }
    }
    return null;
  });
  if (withEx) {
    // 显式带 view=dict：否则会沿用上次记住的视图（可能是翻译页）
    await page.evaluate(() => { localStorage.setItem("hanfr.ui.view", "dict"); });
    await page.goto(`${BASE}/?q=${encodeURIComponent(withEx.zh)}&view=dict`,
      { waitUntil: "networkidle2" });
    await new Promise(r => setTimeout(r, 700));
    await page.screenshot({ path: path.join(OUT, "example-liaison.png"), fullPage: true });
    console.log(`✓ example-liaison.png  （"${withEx.zh}"，${withEx.n} 处联诵）`);
  } else {
    console.log("· 尚无例句数据，跳过联诵截图（例句管线跑完后再拍）");
  }

  console.log(errors.length ? `\n✗ 控制台错误 ${errors.length}：${errors[0].slice(0,120)}` : "\n✓ 全程 0 控制台错误");
  await browser.close();
})();