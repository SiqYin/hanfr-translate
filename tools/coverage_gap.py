#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coverage_gap.py — 分析例句覆盖率缺口

问题：
  例句池在涨（20 万+），但词条覆盖率停在 88%，说明涨出来的句子
  对应的词头跟缺口的词头**不是同一批**。

  要补到 95%，必须知道：
    1. 哪些词条还没有例句？
    2. 这些词条在语料池里有没有可用句子？
    3. 如果没有，是要补造句子，还是根本造不出来？

    python tools/coverage_gap.py
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
SRC = os.path.join(ROOT, "app", "zhfr.js")
CORPUS = os.path.join(ROOT, "data", "corpus_zh.jsonl")
CACHE = os.path.join(ROOT, "data", "cache", "examples_fr.jsonl")
OUT = os.path.join(ROOT, "data", "coverage_gap.tsv")


def main():
    src = io.open(SRC, encoding="utf-8").read()
    m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
    ZF = json.loads(m.group(1))

    have = set()
    for e in ZF:
        if e[6]:
            have.add(e[1])

    missing = [e for e in ZF if not e[6]]
    print("词条 %d，已有例句 %d，缺 %d（当前覆盖 %.2f%%）"
          % (len(ZF), len(have), len(missing), 100 * len(have) / len(ZF)))

    # 语料池里有哪些词头
    corpus_heads = collections.Counter()
    if os.path.exists(CORPUS):
        for line in io.open(CORPUS, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            corpus_heads[d.get("zh", "")] += 1

    # 已译缓存里有哪些
    done_heads = set()
    if os.path.exists(CACHE):
        for line in io.open(CACHE, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                done_heads.add(json.loads(line).get("zh", ""))
            except Exception:
                continue

    in_corpus = [e for e in missing if e[1] in corpus_heads]
    not_in_corpus = [e for e in missing if e[1] not in corpus_heads]

    print("\n缺口分析：")
    print("  语料池里有句子（等翻译）  %d" % len(in_corpus))
    print("  语料池里没有（需造句子）  %d" % len(not_in_corpus))
    print("  已译但未挂载            %d" % len([e for e in missing if e[1] in done_heads]))

    # 未在语料池里的，看看是什么词
    print("\n不在语料池的缺口词抽样：")
    for e in not_in_corpus[:25]:
        print("  %-10s %s" % (e[1], (e[3] or "")[:32]))

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("词头\t在语料池\t法语首义项\n")
        for e in missing:
            f.write("%s\t%s\t%s\n"
                    % (e[1], "是" if e[1] in corpus_heads else "否",
                       (e[3] or "")[:40]))
    print("\n明细 -> %s" % OUT)


if __name__ == "__main__":
    main()