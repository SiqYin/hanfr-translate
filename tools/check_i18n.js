/* check_i18n.js — 校验四语言键位完全对齐
 *
 * 汉南的教训：i18n 用单字母全局函数名 t()，被局部变量遮蔽后整个翻译页崩掉。
 * 这里的风险不同：某一语言漏一个键，界面上就会出现裸键名（app_name），
 * 或者退化成简体，用户看不出是 bug。
 *
 *   node tools/check_i18n.js
 */
"use strict";

const path = require("path");
const fs = require("fs");

const file = path.join(__dirname, "..", "app", "i18n.js");
const src = fs.readFileSync(file, "utf8");

// 在沙箱里跑 i18n.js，拿到 DICT
const sandbox = { window: {}, document: null, navigator: { language: "zh-Hans" }, localStorage: null };
const fn = new Function("window", "navigator", "localStorage", "document", src + "\nreturn window.I18N;");
let I18N;
try {
  I18N = fn(sandbox.window, sandbox.navigator, null, null);
} catch (e) {
  // i18n.js 里有 document/localStorage 调用，允许在最后抛错但我们已拿到 window.I18N
  I18N = sandbox.window.I18N;
}
if (!I18N) {
  console.error("无法加载 i18n.js");
  process.exit(1);
}

const langs = I18N.langs;
const dict = I18N.DICT;
const base = langs[0];
const baseKeys = Object.keys(dict[base]).sort();

let fail = 0;
console.log("语言：" + langs.join(" / "));
console.log("基准（" + base + "）键数：" + baseKeys.length + "\n");

for (const l of langs.slice(1)) {
  const keys = new Set(Object.keys(dict[l]));
  const missing = baseKeys.filter(k => !keys.has(k));
  const extra = [...keys].filter(k => !baseKeys.includes(k));
  if (missing.length) {
    fail++;
    console.log("✗ " + l + " 缺 " + missing.length + " 键：" + missing.join(", "));
  }
  if (extra.length) {
    fail++;
    console.log("✗ " + l + " 多 " + extra.length + " 键：" + extra.join(", "));
  }
  if (!missing.length && !extra.length) {
    console.log("✓ " + l + " 键位对齐（" + keys.size + "）");
  }
}

// 空值检查
for (const l of langs) {
  const empty = Object.entries(dict[l]).filter(([k, v]) => !String(v || "").trim()).map(([k]) => k);
  if (empty.length) {
    fail++;
    console.log("✗ " + l + " 空值：" + empty.join(", "));
  }
}

// 占位符一致性：同一键在各语言的 {var} 集合应相同
const PH = /\{(\w+)\}/g;
for (const k of baseKeys) {
  const sets = {};
  for (const l of langs) {
    const v = String(dict[l][k] || "");
    const m = new Set();
    let x;
    while ((x = PH.exec(v))) m.add(x[1]);
    PH.lastIndex = 0;
    sets[l] = [...m].sort().join(",");
  }
  const uniq = new Set(Object.values(sets));
  if (uniq.size > 1) {
    fail++;
    console.log("✗ 键 " + k + " 占位符不一致：" +
      langs.map(l => l + "={" + sets[l] + "}").join("  "));
  }
}

console.log("");
if (fail) {
  console.log("失败 " + fail + " 项");
  process.exit(1);
} else {
  console.log("四语言键位完全对齐，占位符一致。");
}