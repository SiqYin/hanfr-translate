#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_coverage_evenness.py — 检查例句覆盖是否均匀

用户要求：例句量要**合适且均匀覆盖所有收词**，不能有的词很多、有的词一条没有。

本脚本回答三个问题：
  1. 每个词条到底有几条例句可用？（语料池里）
  2. 缺口是哪些词？（哪些词造不出例句）
  3. 分布是否偏斜？（少数词占用大量句子，多数词没有）

    python tools/analyze_coverage_evenness.py
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
DONE = os.path.join(ROOT, "data", "cache", "examples_fr.jsonl")


def main():
    src = io.open(SRC, encoding="utf-8").read()
    ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S).group(1))
    heads = [e[1] for e in ZF]

    # 语料池：每个词头有几句话
    corpus_cnt = collections.Counter()
    if os.path.exists(CORPUS):
        for line in io.open(CORPUS, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            corpus_cnt[d.get("zh", "")] += 1

    # 已译：每个词头几条
    done_cnt = collections.Counter()
    if os.path.exists(DONE):
        for line in io.open(DONE, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                done_cnt[json.loads(line).get("zh", "")] += 1
            except Exception:
                continue

    with_ex = sum(1 for h in heads if done_cnt.get(h, 0) > 0)
    no_corpus = [h for h in heads if corpus_cnt.get(h, 0) == 0]
    has_corpus_no_done = [h for h in heads
                          if corpus_cnt.get(h, 0) > 0 and done_cnt.get(h, 0) == 0]

    print("=" * 66)
    print("例句覆盖均匀性分析")
    print("=" * 66)
    print("词条总数              %6d" % len(heads))
    print("已有例句              %6d  (%.2f%%)" % (with_ex, 100 * with_ex / len(heads)))
    print("无例句                %6d" % (len(heads) - with_ex))
    print()
    print("缺口拆解：")
    print("  语料池里就没有句子   %6d" % len(no_corpus))
    print("  有句子但还没译       %6d" % len(has_corpus_no_done))
    print()

    # 覆盖偏斜：已译句子的分布
    dist = collections.Counter()
    for h in heads:
        n = done_cnt.get(h, 0)
        if n == 0:
            dist["0"] += 1
        elif n == 1:
            dist["1"] += 1
        elif n <= 3:
            dist["2-3"] += 1
        elif n <= 10:
            dist["4-10"] += 1
        else:
            dist[">10"] += 1
    print("每词已译句数分布：")
    for k in ["0", "1", "2-3", "4-10", ">10"]:
        print("  %-6s %6d  (%.1f%%)"
              % (k, dist[k], 100 * dist[k] / len(heads)))
    print()

    top = done_cnt.most_common(10)
    print("例句最多的词（前 10）：")
    for w, n in top:
        print("  %-8s %4d 句" % (w, n))

    if no_corpus:
        print()
        print("语料池无句子的词（前 30）：")
        for h in no_corpus[:30]:
            e = next((x for x in ZF if x[1] == h), None)
            print("  %-8s %s" % (h, (e[3] or "")[:34] if e else ""))


if __name__ == "__main__":
    main()
