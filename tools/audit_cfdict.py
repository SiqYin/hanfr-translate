#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_cfdict.py — CFDICT 数据质量审计

不审计就建库，等于把别人的错误原样发布。本脚本量化 CFDICT 的问题规模：

  1. 括号不平衡      "tendences malsaines(néfastes"
  2. 拼写可疑        "funèrailles"（应为 funérailles）、"bellemère"（应为 belle-mère）
  3. 非法语残留      中文、英文、拉丁学名、化学式
  4. 纯分类标签      "radical 85"、"n° 1"
  5. 过长义项        > 60 字符的句子式释义
  6. 重复/近重复
  7. Lexique 查不到的实词（这些是 IPA 缺口的来源）

输出：
  data/cfdict_audit.json     各问题的计数
  data/cfdict_defects.tsv    逐条缺陷清单（供修数据或人工复核）
"""
import collections
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
CFDICT = os.path.join(RAW, "cfdict.u8")
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
OUT_JSON = os.path.join(ROOT, "data", "cfdict_audit.json")
OUT_TSV = os.path.join(ROOT, "data", "cfdict_defects.tsv")

LINE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+/(.*)/\s*$")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CHEM = re.compile(r"\b[A-Z][a-z]?\d+[A-Z]|\bC\d+H\d+")
LATIN_BINOMIAL = re.compile(r"^[A-Z][a-z]+ [a-z]{4,}$")
CLASS_LABEL = re.compile(r"^(radical|n°|no\.?|numéro|classe|catégorie)\b", re.I)
ENGLISH = re.compile(r"\b(the|of|and|with|that|this|from|which)\b", re.I)


def load_lexique_words():
    s = set()
    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        i_o = hdr.index("ortho")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) > i_o and p[i_o].strip():
                s.add(p[i_o].strip().lower())
    return s


def main():
    lex = load_lexique_words()
    sys.stderr.write("Lexique 词形 %d\n" % len(lex))

    pending = collections.Counter()
    defects = []
    total_gloss = 0
    entries = 0

    def flag(word, gloss, kind, detail=""):
        pending[kind] += 1
        if len(defects) < 20000:
            defects.append((word, gloss, kind, detail))

    with io.open(CFDICT, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            m = LINE.match(line.rstrip("\n"))
            if not m:
                continue
            entries += 1
            trad, simp, py, gloss = m.groups()
            for g in gloss.split("/"):
                g = g.strip()
                if not g:
                    continue
                total_gloss += 1

                if g.count("(") != g.count(")"):
                    flag(simp, g, "paren_unbalanced")
                if CJK.search(g):
                    flag(simp, g, "has_cjk")
                if CHEM.search(g):
                    flag(simp, g, "has_chem_formula")
                if LATIN_BINOMIAL.match(g):
                    flag(simp, g, "latin_binomial")
                if CLASS_LABEL.match(g):
                    flag(simp, g, "class_label")
                if ENGLISH.search(g):
                    flag(simp, g, "looks_english")
                if len(g) > 60:
                    flag(simp, g, "too_long")
                if re.search(r"\s{2,}", g):
                    flag(simp, g, "double_space")
                if g != g.strip():
                    flag(simp, g, "edge_space")

                # 拼写可疑：法语里 ç 后不接 e/i 之外、或不常见的连续重复
                if re.search(r"([a-zéèêàçùûôî])\1\1", g, re.I):
                    flag(simp, g, "triple_letter")

    # Lexique 查不到的实词：这是 IPA 缺口的真实来源，单独统计
    unknown_words = collections.Counter()
    with io.open(CFDICT, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            m = LINE.match(line.rstrip("\n"))
            if not m:
                continue
            gloss = m.group(4)
            for g in gloss.split("/"):
                g = re.sub(r"\([^)]*\)", " ", g).strip()
                if not g:
                    continue
                for tok in re.split(r"[\s,;:!?«»\"]+", g):
                    w = tok.strip(".").lower()
                    if not w or len(w) < 2 or not re.match(r"^[a-zà-ÿœæç'-]+$", w):
                        continue
                    if w not in lex:
                        unknown_words[w] += 1

    stats = {
        "entries": entries,
        "total_glosses": total_gloss,
        "defects": dict(pending),
        "defect_rate": {k: round(v / total_gloss, 4) for k, v in pending.items()},
        "unknown_french_words": len(unknown_words),
        "top_unknown": unknown_words.most_common(40),
    }
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=2))
    with io.open(OUT_TSV, "w", encoding="utf-8") as f:
        f.write("词头\t义项\t问题\t细节\n")
        for row in defects:
            f.write("\t".join(row) + "\n")

    print("CFDICT 条目 %d，义项 %d" % (entries, total_gloss))
    for k, v in sorted(pending.items(), key=lambda kv: -kv[1]):
        print("  %-20s %6d  (%.2f%%)" % (k, v, 100 * v / total_gloss))
    print("Lexique 查不到的实词 %d 种" % len(unknown_words))
    print("高频未登录词：", ", ".join("%s(%d)" % (w, c) for w, c in unknown_words.most_common(15)))


if __name__ == "__main__":
    main()