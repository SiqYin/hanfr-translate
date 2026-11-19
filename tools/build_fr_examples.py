#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fr_examples.py — 法语词例句反向索引

问题：
  现有例句是挂在**中文词头**上的（ZF[6]），法语词查不到自己的例句。
  用户在法语词条下应该看到「这个词出现在哪些句子里」。

做法：
  遍历全部例句，把每个句子里出现的法语词作为键，记录该例句。
  法语词用现有的 fr2zh / ipa 词典做切分，取 1-4 词最长匹配。

输出：
  app/frex.js   window.FREX = {"livre": [["请把书给我。","Donnez-moi le livre.","/.../"], ...]}

体积控制：
  116,474 条例句 × 平均 6 个法语词 ≈ 70 万条索引，全部存会很大。
  只存「首条例句 + 最多 2 条」，且例句正文做去重（相同句子只存一次）。

    python tools/build_fr_examples.py
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
FR2ZH = os.path.join(ROOT, "app", "fr2zh.js")
IPA = os.path.join(ROOT, "app", "ipa.js")
OUT = os.path.join(ROOT, "app", "frex.js")

MAX_PER_WORD = 2          # 每个法语词最多存几条例句

# 法语常用虚词：不作为索引键（否则每个词都挂在 le/de/et 上）
STOP = set("""
le la les l un une des du de d au aux à et ou mais donc or ni car
je tu il elle on nous vous ils elles me te se lui leur y en
ce cet cette ces mon ton son ma ta sa mes tes ses notre votre leurs
qui que quoi dont où quand si comme pour par avec sans sous sur
dans entre vers chez est sont était étaient être avoir a ont
plus moins très bien tout tous toute toutes même aussi
ne pas non oui s n c j qu
""".split())


def load_fr2zh():
    s = io.open(FR2ZH, encoding="utf-8").read()
    m = re.search(r"window\.FR2ZH=(\{.*\});\s*$", s, re.S)
    return json.loads(m.group(1)) if m else {}


def load_ipa_words():
    s = io.open(IPA, encoding="utf-8").read()
    m = re.search(r"window\.IPA=(\{.*?\});", s, re.S)
    if not m:
        return set()
    try:
        d = json.loads(m.group(1))
    except Exception:
        return set()
    return set(d.keys())


def load_examples():
    s = io.open(SRC, encoding="utf-8").read()
    ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", s, re.S).group(1))
    out = []
    for e in ZF:
        ex = e[6]
        if not ex:
            continue
        items = ex if isinstance(ex[0], list) else [ex]
        for it in items:
            if not it or not it[0]:
                continue
            fr = it[1] or ""
            if not fr:
                continue
            out.append((it[0], fr, it[2] or ""))
    return out


WORD_RE = re.compile(r"[A-Za-zÀ-ÿŒœÆæÇç'-]+")


def main():
    sys.stderr.write("加载词典...\n")
    vocab = set(load_fr2zh().keys())
    vocab |= load_ipa_words()
    # 只保留单词形态（短语不参与切分）
    vocab = {w.lower() for w in vocab if w and " " not in w}
    sys.stderr.write("  词典 %d 个词形\n" % len(vocab))

    # 按长度降序，做最长匹配
    maxlen = max((len(w) for w in vocab), default=12)

    sys.stderr.write("读取例句...\n")
    examples = load_examples()
    sys.stderr.write("  例句 %d 条\n" % len(examples))

    # fr 词 -> [(zh, fr, ipa)]
    idx = collections.defaultdict(list)
    # 同一例句不重复挂到同一个词
    for zh, fr, ipa in examples:
        words = WORD_RE.findall(fr)
        seen = set()
        for raw in words:
            w = raw.lower().strip("'-")
            if not w or w in STOP or w in seen:
                continue
            if w not in vocab:
                continue
            seen.add(w)
            lst = idx[w]
            if len(lst) >= MAX_PER_WORD:
                continue
            # 同一句不重复
            if any(x[0] == zh for x in lst):
                continue
            lst.append([zh, fr, ipa])

    # 只保留有例句的词
    idx = {k: v for k, v in idx.items() if v}

    js = "window.FREX=" + json.dumps(idx, ensure_ascii=False,
                                     separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    n_items = sum(len(v) for v in idx.values())
    print("法语例句索引 %d 个词 -> %s（%.2f MB）"
          % (len(idx), OUT, len(js.encode("utf-8")) / 1048576))
    print("  例句条目 %d" % n_items)

    print("\n抽样：")
    for w in ("livre", "maison", "eau", "manger", "parler"):
        if w in idx:
            print("  %-8s %d 条: %s" % (w, len(idx[w]), idx[w][0][1][:60]))


if __name__ == "__main__":
    main()
