#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_h_aspire.py — 对 h aspiré 表里的高频词逐个核对维基原文

背景：
  "Termes en français à h aspiré" 分类本身是权威的，但**一个词条可能有多个词性**，
  其中只有部分词性是 h aspiré。典型例子 hier：
      副词 hier → h muet（d'hier / i.jɛʁ）
      动词 hier → h aspiré（je hie / je hi）
  直接拿分类成员当"这个词就是 h aspiré"，会把 d'hier 判成禁配。

做法：
  1. 用 Lexique383 的词频取表内高频词（这些才会真的出现在例句里）；
  2. 逐个拉 fr.wiktionary 的 wikitext，找法语章节里的 {{h muet}} / {{h aspiré}}；
  3. 同时出现两者 → dual，写进 override，标 pending 由人复核；
     只有 h aspiré → 确认；
     只有 h muet → 剔除（分类误收）。

输出：
  data/fr_h_aspire_override.tsv   人工复核用：词<TAB>状态<TAB>依据
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "data", "fr_h_aspire.tsv")
LEXIQUE = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据", "Lexique383.tsv"))
OUT = os.path.join(ROOT, "data", "fr_h_aspire_override.tsv")

API = "https://fr.wiktionary.org/w/api.php"
UA = "HanFrDictBuilder/0.1 (local build; h-aspire verification)"

# 取多少高频词去核（越多越慢；500 条覆盖绝大多数实际出现场景）
TOP_N = 500


def load_words():
    ws = []
    with io.open(TSV, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            ws.append(line.split("\t")[0].strip())
    return ws


def load_freq():
    """ortho -> 最大词频（取 films+livres 的 lemma 频次，简单稳健）"""
    freq = {}
    with io.open(LEXIQUE, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        try:
            i_o = header.index("ortho")
            i_f1 = header.index("freqlemlivres")
            i_f2 = header.index("freqlemfilms2")
        except ValueError:
            return freq
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_f1, i_f2):
                continue
            w = p[i_o].strip().lower()
            if not w:
                continue
            try:
                v = float(p[i_f1] or 0) + float(p[i_f2] or 0)
            except ValueError:
                v = 0.0
            if v > freq.get(w, -1):
                freq[w] = v
    return freq


def wikitext(page, tries=4):
    q = urllib.parse.urlencode({"action": "parse", "page": page,
                                "prop": "wikitext", "format": "json",
                                "formatversion": 2})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.loads(r.read().decode("utf-8"))
            return ((j.get("parse") or {}).get("wikitext") or "")
        except Exception as e:
            if i == tries - 1:
                return ""
            time.sleep(2.5 * (i + 1))
    return ""


def french_section(w):
    """仅保留 == {{langue|fr}} == 到下一个 == {{langue|xx}} == 之间的内容。"""
    m = re.search(r"==\s*\{\{langue\|fr\}\}\s*==", w)
    if not m:
        return ""
    rest = w[m.end():]
    n = re.search(r"\n==\s*\{\{langue\|", rest)
    return rest[:n.start()] if n else rest


def classify(w):
    fr = french_section(w)
    if not fr:
        return "unknown", "无法语章节"
    muet = "{{h muet}}" in fr
    aspir = "{{h aspiré}}" in fr
    # pron 里出现 i.jɛʁ 这类以元音起头且带 h muet 模板的，也算 muet 证据
    if muet and aspir:
        return "dual", "同时有 h muet 与 h aspiré"
    if aspir:
        return "aspire", "仅 h aspiré"
    if muet:
        return "muet", "仅 h muet"
    return "unknown", "法语章节未标 h 类型"


def main():
    words = load_words()
    freq = load_freq()
    ranked = sorted(words, key=lambda w: -freq.get(w.lower(), 0))
    top = ranked[:TOP_N]
    sys.stderr.write("表中 %d 词，核对高频前 %d 条\n" % (len(words), len(top)))

    results = {}
    for i, w in enumerate(top, 1):
        wt = wikitext(w)
        st, why = classify(wt) if wt else ("unknown", "页面拉取失败")
        results[w] = (st, why)
        if i % 25 == 0:
            sys.stderr.write("  已核 %d/%d\n" % (i, len(top)))
        time.sleep(0.35)          # 温和节流，避免 Wikimedia 限流

    dual = [(w, why) for w, (st, why) in results.items() if st == "dual"]
    muet = [(w, why) for w, (st, why) in results.items() if st == "muet"]
    unk = [(w, why) for w, (st, why) in results.items() if st == "unknown"]

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("# h aspiré 复核结果（tools/verify_h_aspire.py 生成）\n")
        f.write("# 格式：词\\t状态\\t依据\\n")
        f.write("# 状态：dual=双状态需人工定夺 / muet=应剔除 / unknown=页面未标\n")
        for w in sorted(results, key=lambda x: (results[x][0], x.lower())):
            st, why = results[w]
            if st == "aspire":
                continue
            f.write("%s\t%s\t%s\n" % (w, st, why))

    sys.stderr.write("\n核对完成：dual %d / muet %d / unknown %d\n"
                     % (len(dual), len(muet), len(unk)))
    if dual:
        sys.stderr.write("双状态词（需人工定夺）：%s\n" % ", ".join(w for w, _ in dual[:20]))
    if muet:
        sys.stderr.write("应剔除（仅 h muet）：%s\n" % ", ".join(w for w, _ in muet[:20]))
    sys.stderr.write("写出 %s\n" % OUT)


if __name__ == "__main__":
    main()