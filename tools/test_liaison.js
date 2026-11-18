/* test_liaison.js — 聯誦引擎測試
 *
 * 為什麼要測試：
 *   聯誦判定是「規則 + 詞表」的組合，任何一條規則回歸都會讓整句讀音錯掉，
 *   而這種錯誤在 UI 上完全看不出來（照樣顯示，只是標錯了）。
 *
 * 用例來源：
 *   法語語法教學中的標準例子，全部是無爭議的。
 *   每條都寫明為什麼是這個分類。
 *
 *   node tools/test_liaison.js
 */
"use strict";

const path = require("path");
const fs = require("fs");
const FRL = require(path.join(__dirname, "..", "app", "liaison.js"));

// ---- 載入 h aspiré 詞表 ----
const TSV = path.join(__dirname, "..", "data", "fr_h_aspire.tsv");
const hAspire = new Set();
if (fs.existsSync(TSV)) {
  for (const line of fs.readFileSync(TSV, "utf8").split("\n")) {
    if (!line || line.startsWith("#")) continue;
    const w = line.split("\t")[0].trim();
    if (w) hAspire.add(w.toLowerCase());
  }
}

let pass = 0, fail = 0;
const failures = [];

function check(left, right, expect, why, opts) {
  const r = FRL.classifyPair(left, right, Object.assign({ hAspire }, opts || {}));
  const ok = r.type === expect;
  if (ok) {
    pass++;
  } else {
    fail++;
    failures.push({ left, right, expect, got: r.type, why, reason: r.reason });
  }
}

function checkPhon(left, right, expectType, expectPhon, why, opts) {
  const r = FRL.classifyPair(left, right, Object.assign({ hAspire }, opts || {}));
  const ok = r.type === expectType && r.phon === expectPhon;
  if (ok) {
    pass++;
  } else {
    fail++;
    failures.push({
      left, right, expect: `${expectType}/${expectPhon}`,
      got: `${r.type}/${r.phon}`, why
    });
  }
}

console.log("h aspiré 詞表載入 " + hAspire.size + " 條\n");

// ================= obligatoire =================
// 限定詞 + 名詞
check("les", "amis", "obligatoire", "複數限定詞 + 元音開頭名詞：les‿amis /le.za.mi/");
check("des", "enfants", "obligatoire", "des‿enfants");
check("un", "homme", "obligatoire", "un‿homme /œ̃.nɔm/");
check("mon", "ami", "obligatoire", "mon‿ami");
check("ces", "arbres", "obligatoire", "ces‿arbres");
// 代詞 + 動詞
check("vous", "avez", "obligatoire", "vous‿avez /vu.za.ve/");
check("nous", "allons", "obligatoire", "nous‿allons");
check("ils", "ont", "obligatoire", "ils‿ont");
check("elle", "est", "obligatoire", "elle‿est");
check("on", "a", "obligatoire", "on‿a");
// 單音節介詞 / 副詞
check("chez", "elle", "obligatoire", "chez‿elle /ʃe.zɛl/");
check("dans", "un", "obligatoire", "dans‿un");
check("sans", "argent", "obligatoire", "sans‿argent");
check("très", "important", "obligatoire", "très‿important /tʁɛ.zɛ̃.pɔʁ.tɑ̃/");
check("bien", "aimable", "obligatoire", "bien‿aimable");
// est / c'est
check("c'est", "un", "obligatoire", "c'est‿un /sɛ.tœ̃/");
check("est", "arrivé", "obligatoire", "est‿arrivé");
// 數詞
check("deux", "ans", "obligatoire", "deux‿ans /dø.zɑ̃/");
check("trois", "enfants", "obligatoire", "trois‿enfants");
// quand
check("quand", "il", "obligatoire", "quand‿il /kɑ̃.til/");

// ================= interdite: h aspiré =================
check("les", "héros", "interdite", "h aspiré：les | héros /le.e.ʁo/");
check("le", "hibou", "interdite", "h aspiré：le | hibou");
check("un", "héros", "interdite", "h aspiré：un | héros");
check("des", "haches", "interdite", "h aspiré：des | haches");
check("les", "hérissons", "interdite", "h aspiré：les | hérissons");
check("en", "haut", "interdite", "h aspiré：en | haut");
check("très", "honteux", "interdite", "h aspiré：très | honteux");

// ================= interdite: 連詞 et =================
check("et", "il", "interdite", "et 之後永不聯誦：et | il /e.il/");
check("et", "elle", "interdite", "et 之後：et | elle");
check("et", "on", "interdite", "et 之後：et | on");
check("et", "ainsi", "interdite", "et 之後：et | ainsi");

// ================= interdite: onze =================
check("les", "onze", "interdite", "onze 前不聯誦：les | onze");
check("de", "onze", "interdite", "onze 前：de | onze");
check("les", "onzième", "interdite", "onzième 前：les | onzième");

// ================= interdite: 單數名詞 + 動詞 =================
check("chat", "est", "interdite", "單數名詞 + 動詞：le chat | est",
  { posLeft: "NOM", posRight: "VER" });
check("enfant", "a", "interdite", "單數名詞 + 動詞：enfant | a",
  { posLeft: "NOM", posRight: "VER" });
// 但形容詞修飾名詞時可聯誦
check("petit", "enfant", "facultative", "形容詞 + 名詞：petit‿enfant（可選）",
  { posLeft: "ADJ", posRight: "NOM" });

// ================= 不該有聯誦 =================
check("chat", "noir", "none", "右詞輔音開頭，無聯誦");
check("livre", "rouge", "none", "右詞輔音開頭");
check("parler", "à", "none", "詞尾 -er 的 r 不聯誦：parler | à");
check("aller", "au", "none", "詞尾 -er：aller | au");

// ================= 音素正確性 =================
checkPhon("les", "amis", "obligatoire", "z", "s -> z");
checkPhon("un", "homme", "obligatoire", "n", "n -> n");
checkPhon("c'est", "un", "obligatoire", "t", "t -> t");
checkPhon("deux", "ans", "obligatoire", "z", "x -> z");
checkPhon("quand", "il", "obligatoire", "t", "d -> t");
checkPhon("neuf", "ans", "obligatoire", "v", "f -> v（neuf ans /nœ.vɑ̃/）");
checkPhon("vingt", "ans", "obligatoire", "t", "vingt -> vɛ̃t");
checkPhon("trop", "aimable", "obligatoire", "p", "trop -> tʁop");
checkPhon("six", "ans", "obligatoire", "z", "six -> siz");
checkPhon("dix", "ans", "obligatoire", "z", "dix -> diz");

// ================= facultative =================
check("enfants", "assistent", "facultative", "複數名詞 + 動詞：可聯誦");
check("maisons", "anciennes", "facultative", "名詞 + 形容詞：可聯誦");

// ================= 省音 =================
function checkElide(word, next, expect, why) {
  const got = FRL.elide(word, next, hAspire);
  const ok = got === expect;
  if (ok) pass++;
  else {
    fail++;
    failures.push({ left: word + " + " + next, right: "", expect, got, why });
  }
}
checkElide("le", "ami", "l'", "le + 元音 -> l'");
checkElide("de", "eau", "d'", "de + 元音 -> d'");
checkElide("que", "il", "qu'", "que + 元音 -> qu'");
checkElide("le", "héros", "le", "h aspiré 不省音：le héros");
checkElide("le", "chat", "le", "輔音開頭不省音");

// ================= 整句標註 =================
function checkSentence(tokens, expectCount, why) {
  const r = FRL.annotate(tokens, { hAspire });
  const ok = r.length === expectCount;
  if (ok) pass++;
  else {
    fail++;
    failures.push({
      left: tokens.join(" "), right: "", expect: expectCount + " 處",
      got: r.length + " 處", why
    });
  }
}
checkSentence(["les", "amis", "sont", "arrivés"], 2, "les‿amis / sont|arrivés（sont 不在 obligatoire 表内，判 facultative，也计入）");
checkSentence(["le", "chat", "est", "noir"], 1, "只有 chat|est 有判定（禁止），其餘無");
checkSentence(["il", "est", "allé"], 2, "il‿est / est‿allé");

// ================= 結果 =================
console.log("通過 " + pass + " / 失敗 " + fail + "\n");
if (fail) {
  console.log("失敗明細：");
  for (const f of failures) {
    console.log("  ✗ 「" + f.left + (f.right ? " " + f.right : "") + "」");
    console.log("     期望 " + f.expect + "，實得 " + f.got);
    console.log("     說明 " + f.why);
  }
  process.exit(1);
} else {
  console.log("全部通過。");
}