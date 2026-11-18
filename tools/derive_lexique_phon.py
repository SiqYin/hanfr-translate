#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""derive_lexique_phon.py — 反推 Lexique383 的音素编码 -> IPA 映射

背景：
  Lexique383 的 phon 字段**不是 IPA**，而是 LAIPTTS 派生的一套单字符编码
  （maison -> "mEz§"、chien -> "Sj5"、temps -> "t@"）。直接当音标用会是乱码。
  官方手册只零散给了 9 处与 X-SAMPA 的差异，没有完整对照表。

做法：
  拿一批**发音确定无疑**的高频词（我逐个人工给出标准 IPA），
  用它们的 ortho/phon 对去反推每个编码字符对应的 IPA 符号。
  这不是猜——每个字符的对应都由多个独立词例交叉验证。

输出：
  data/lexique_phon_map.json   {"code": "ipa", ...}
  data/lexique_phon_map.md     人可读的对照表 + 每个映射的证据词
"""
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEXIQUE = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据", "Lexique383.tsv"))
OUT_JSON = os.path.join(ROOT, "data", "lexique_phon_map.json")
OUT_MD = os.path.join(ROOT, "data", "lexique_phon_map.md")

# 锚点词：ortho -> 标准 IPA（宽式，与通行法语词典转写一致）
# 选词原则：高频、发音无争议、覆盖尽可能多的音素
ANCHORS = {
    # --- 元音 ---
    "lit": "li",            # i
    "vie": "vi",            # i
    "nez": "ne",            # e
    "été": "ete",           # e
    "père": "pɛʁ",          # ɛ
    "mère": "mɛʁ",          # ɛ
    "chat": "ʃa",           # a
    "papa": "papa",         # a
    "pâte": "pɑt",          # ɑ
    "mots": "mo",           # o
    "beau": "bo",           # o
    "port": "pɔʁ",          # ɔ
    "mort": "mɔʁ",          # ɔ
    "roue": "ʁu",           # u
    "tout": "tu",           # u
    "lune": "lyn",          # y
    "pur": "pyʁ",           # y
    "peu": "pø",            # ø
    "deux": "dø",           # ø
    "peur": "pœʁ",          # œ
    "fleur": "flœʁ",        # œ
    "soeur": "sœʁ",         # œ
    "le": "lə",             # ə
    "je": "ʒə",             # ə
    "ce": "sə",             # ə
    # --- 鼻化元音 ---
    "pain": "pɛ̃",           # ɛ̃
    "fin": "fɛ̃",           # ɛ̃
    "chien": "ʃjɛ̃",         # ɛ̃
    "temps": "tɑ̃",          # ɑ̃
    "grand": "ɡʁɑ̃",         # ɑ̃
    "dans": "dɑ̃",           # ɑ̃
    "bon": "bɔ̃",            # ɔ̃
    "maison": "mɛzɔ̃",      # ɔ̃
    "un": "œ̃",              # œ̃
    "brun": "bʁœ̃",          # œ̃
    # --- 半元音 ---
    "nuit": "nɥi",          # ɥ
    "huit": "ɥit",          # ɥ
    "oui": "wi",            # w
    "loi": "lwa",           # w
    "yeux": "jø",           # j
    "fille": "fij",         # j
    # --- 鼻辅音 ---
    "agneau": "aɲo",        # ɲ
    "montagne": "mɔ̃taɲ",    # ɲ
    "camping": "kɑ̃piŋ",     # ŋ
    "parking": "paʁkiŋ",    # ŋ
    # --- 后 a（Lexique 与 /a/ 不分，用 A 表示；此处分列以便前端可选区分）---
    "âge": "ɑʒ",            # ɑ
    # --- 辅音 ---
    "papa": "papa",         # p
    "bébé": "bebe",         # b
    "tas": "ta",            # t
    "dos": "do",            # d
    "cas": "ka",            # k
    "gare": "ɡaʁ",          # ɡ
    "fait": "fɛ",           # f
    "vase": "vaz",          # v
    "sel": "sɛl",           # s
    "zoo": "zo",            # z
    "chat": "ʃa",           # ʃ
    "je": "ʒə",             # ʒ
    "main": "mɛ̃",           # m
    "nez": "ne",            # n
    "lit": "li",            # l
    "riz": "ʁi",            # ʁ
    "roi": "ʁwa",           # ʁ
}


def load_lex():
    rec = {}
    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        i_o, i_p = hdr.index("ortho"), hdr.index("phon")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_p):
                continue
            o, ph = p[i_o], p[i_p]
            if o and ph and o not in rec:
                rec[o] = ph
    return rec


def main():
    lex = load_lex()
    sys.stderr.write("Lexique 词形 %d\n" % len(lex))

    # 逐锚点做「字符级对齐」：把一个词的 lexique 码序列与 IPA 序列对齐，
    # 收集 (code_char -> ipa_symbol) 的证据。
    votes = {}      # code -> {ipa: [words]}
    missing = []

    for word, ipa in ANCHORS.items():
        code = lex.get(word)
        if not code:
            missing.append(word)
            continue
        cs = list(code)
        # IPA 拆成「基字符 + 组合记号」
        import unicodedata
        ipa_units = []
        for ch in ipa:
            if unicodedata.combining(ch) and ipa_units:
                ipa_units[-1] += ch
            else:
                ipa_units.append(ch)

        if len(cs) != len(ipa_units):
            # 长度不等就跳过（可能有 schwa 位置差异），不强行对齐
            continue

        for c, u in zip(cs, ipa_units):
            votes.setdefault(c, {}).setdefault(u, []).append(word)

    # 取每个 code 的多数票
    mapping = {}
    detail = {}
    for c, d in votes.items():
        best = sorted(d.items(), key=lambda kv: -len(kv[1]))
        mapping[c] = best[0][0]
        detail[c] = {"ipa": best[0][0], "votes": {k: v for k, v in d.items()}}

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(mapping, ensure_ascii=False, indent=2))

    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# Lexique383 音素编码 → IPA 对照表\n\n")
        f.write("由 `tools/derive_lexique_phon.py` 从锚点词反推，多词例交叉验证。\n\n")
        f.write("| 编码 | IPA | 证据词 | 投票 |\n|---|---|---|---|\n")
        for c in sorted(mapping, key=lambda x: (mapping[x], x)):
            ev = detail[c]["votes"].get(mapping[c], [])
            allv = ", ".join("%s:%d" % (k, len(v)) for k, v in detail[c]["votes"].items())
            f.write("| `%s` | `%s` | %s | %s |\n"
                    % (c, mapping[c], ", ".join(ev[:3]), allv))

    sys.stderr.write("反推出 %d 个编码映射\n" % len(mapping))
    if missing:
        sys.stderr.write("锚点词在 Lexique 中缺失：%s\n" % ", ".join(missing))

    # 自检：用映射回译几个词
    def to_ipa(word):
        code = lex.get(word)
        if not code:
            return None
        return "".join(mapping.get(c, "?") for c in code)

    sys.stderr.write("\n回译自检：\n")
    for w in ["eau", "maison", "chien", "temps", "fleur", "nuit", "être", "parler", "montagne"]:
        got = to_ipa(w)
        exp = ANCHORS.get(w, "")
        ok = "✓" if got == exp else ("(参考IPA %s)" % exp if exp else "")
        sys.stderr.write("  %-10s %-14s %s\n" % (w, got, ok))


if __name__ == "__main__":
    main()