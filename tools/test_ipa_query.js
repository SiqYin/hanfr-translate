/* test_ipa_query.js — 音标查询功能测试
 *
 * 覆盖：
 *   1. 单词音标（含变体字母：cœur/coeur、élève/eleve、français/francais）
 *   2. 整句音标 + 联诵内联标记
 *   3. 大小写不敏感、复数回落、省音缩合、连字符复合词
 *
 *   node tools/test_ipa_query.js
 */
"use strict";

const path = require("path");
const fs = require("fs");
const vm = require("vm");

const APP = path.join(__dirname, "..", "app");

// 用 vm 在沙箱里加载浏览器端脚本
const sandbox = { window: {}, console };
sandbox.window = sandbox;
vm.createContext(sandbox);

for (const f of ["h_aspire.js", "ipa.js", "liaison.js", "ipa_query.js"]) {
  const p = path.join(APP, f);
  if (!fs.existsSync(p)) {
    console.error("缺文件：" + p);
    process.exit(1);
  }
  vm.runInContext(fs.readFileSync(p, "utf8"), sandbox, { filename: f });
}

const IQ = sandbox.IPAQuery;
if (!IQ) {
  console.error("IPAQuery 未加载");
  process.exit(1);
}

// 初始化 h aspiré
IQ.setHAspire(new Set((sandbox.H_ASPIRE || []).map(w => String(w).toLowerCase())));

let pass = 0, fail = 0;
const fails = [];

function eq(actual, expected, label) {
  if (actual === expected) {
    pass++;
  } else {
    fail++;
    fails.push({ label, expected, actual });
  }
}

function has(actual, needle, label) {
  if (String(actual || "").indexOf(needle) > -1) {
    pass++;
  } else {
    fail++;
    fails.push({ label, expected: "包含 " + needle, actual });
  }
}

console.log("音标词典词形：" + IQ.size() + "\n");

// ---------------- 1. 基本单词 ----------------
// 期望值用「真实发音」鼻化元音体系：
//   ɛ̃/œ̃ -> ã    ɑ̃ -> ɒ̃    ɔ̃ -> õ
console.log("【单词音标】");
eq(IQ.wordIpa("maison"), "mɛzõ", "maison");
eq(IQ.wordIpa("chien"), "ʃjã", "chien");
eq(IQ.wordIpa("fleur"), "flœʁ", "fleur");
eq(IQ.wordIpa("nuit"), "nɥi", "nuit");
eq(IQ.wordIpa("temps"), "tɒ̃", "temps");
eq(IQ.wordIpa("eau"), "o", "eau");
eq(IQ.wordIpa("être"), "ɛtʁ", "être");
eq(IQ.wordIpa("parler"), "paʁle", "parler");

// ---------------- 2. 变体字母兼容 ----------------
console.log("【变体字母兼容】");
// œ vs oe
eq(IQ.wordIpa("cœur"), IQ.wordIpa("coeur"), "cœur = coeur");
eq(IQ.wordIpa("œuvre"), IQ.wordIpa("oeuvre"), "œuvre = oeuvre");
eq(IQ.wordIpa("sœur"), IQ.wordIpa("soeur"), "sœur = soeur");
// 去变音符号：eleve 应能查到 ÉLÈVE 类词条的音标（不要求与带调输入逐字相同，
// 因为 élève/élevé 折叠冲突，取到哪个都算命中）
const e1 = IQ.wordIpa("élève");
const e2 = IQ.wordIpa("eleve");
eq(e2.length > 0, true, "eleve 能查到音标（去变音符号）");
eq(["elɛv", "eləve", "ɛləve", "elɛve"].indexOf(e2) > -1, true,
   "eleve 音标在合理集合内（实得 " + e2 + "）");
eq(IQ.wordIpa("français"), IQ.wordIpa("francais"), "français = francais");
eq(IQ.wordIpa("garçon"), IQ.wordIpa("garcon"), "garçon = garcon");
eq(IQ.wordIpa("hôtel"), IQ.wordIpa("hotel"), "hôtel = hotel");
eq(IQ.wordIpa("université"), IQ.wordIpa("universite"), "université = universite");
// 大小写
eq(IQ.wordIpa("Maison"), IQ.wordIpa("maison"), "大小写不敏感");
eq(IQ.wordIpa("PARIS"), IQ.wordIpa("paris"), "全大写");

// ---------------- 3. 词形回落 ----------------
console.log("【词形回落】");
has(IQ.wordIpa("maisons"), "mɛz", "复数 maisons");
has(IQ.wordIpa("livres"), "livʁ", "复数 livres");
// 省音缩合
eq(IQ.wordIpa("l'eau"), "lo", "l'eau -> lo");
// 连字符复合词：法语音标不保留连字符，直接连写（peut-être -> pøtɛtʁ）
eq(IQ.wordIpa("peut-être"), "pøtɛtʁ", "peut-être 连写");
eq(IQ.wordIpa("peut-être").indexOf("-"), -1, "音标里不保留连字符");

// ---------------- 4. 整句音标 ----------------
console.log("【整句音标】");
const s1 = IQ.sentenceIpa("Nous sommes allés au parc.");
eq(s1.ok, true, "整句无缺音标");
has(s1.ipa, "nu", "整句含 nous");
has(s1.marked, "‿", "整句有联诵标记");
has(s1.marked, ".", "整句保留句号");

// 强制联诵：les amis
const s2 = IQ.sentenceIpa("les amis");
has(s2.marked, "lez‿ami", "les‿amis 联诵合并");

// 禁止联诵：et il
const s3 = IQ.sentenceIpa("et il");
has(s3.marked, "|", "et | il 禁止联诵");

// h aspiré：les héros
const s4 = IQ.sentenceIpa("les héros");
has(s4.marked, "|", "les | héros 禁止联诵");

// 单句判定
eq(IQ.looksLikeSentence("maison"), false, "单词不判为句子");
eq(IQ.looksLikeSentence("Nous allons au parc."), true, "多词判为句子");

// ---------------- 5. 查不到时不编造 ----------------
console.log("【缺失处理】");
const s5 = IQ.sentenceIpa("xyzzyqqq");
eq(s5.ok, false, "无法识别的词标记为缺失");
eq(s5.missing.length > 0, true, "缺失词已列出");

console.log("");
console.log("通过 " + pass + " / 失败 " + fail);
if (fail) {
  console.log("\n失败明细：");
  for (const f of fails) {
    console.log("  ✗ " + f.label);
    console.log("      期望 " + JSON.stringify(f.expected) + "  实得 " + JSON.stringify(f.actual));
  }
  process.exit(1);
} else {
  console.log("全部通过。");
}