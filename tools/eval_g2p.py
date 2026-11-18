#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_g2p.py — 用 Lexique383 的真实音标，量化规则 G2P 的准确率

问题：
  Lexique383 覆盖 83% 的词条，剩余 17%（专业词、派生词、罕见词）没有音标。
  能不能用规则 G2P 补这 17%？

  不能拍脑袋决定。用户的要求是「不确定的音标标待核，不得编造」。
  规则 G2P 如果准确率不够，用它填充就等于编造。

做法：
  在 Lexique383 有真实音标的词上跑 G2P，逐条比对。
  准确率高 → 可作为第二来源；准确率低 → 只能标待核。

输出：
  data/g2p_accuracy.json   准确率与分桶统计
  data/g2p_errors.tsv      错误样例（供改进规则或人工核对）
"""
import io
import json
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
LEXIQUE = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据", "Lexique383.tsv"))
OUT_JSON = os.path.join(ROOT, "data", "g2p_accuracy.json")
OUT_ERR = os.path.join(ROOT, "data", "g2p_errors.tsv")

from g2p_fr import g2p, lex_to_ipa          # noqa: E402


def main(n_sample=3000, seed=20261118):
    rows = []
    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        i_o, i_p = hdr.index("ortho"), hdr.index("phon")
        seen = set()
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_p):
                continue
            o, ph = p[i_o].strip(), p[i_p].strip()
            if not o or not ph or o in seen:
                continue
            # 只评估纯字母词（带连字符/空格的另算）
            if not o.replace("-", "").replace("'", "").isalpha():
                continue
            seen.add(o)
            rows.append((o, ph))

    random.seed(seed)
    sample = random.sample(rows, min(n_sample, len(rows)))
    sys.stderr.write("评估样本 %d 条（总词形 %d）\n" % (len(sample), len(rows)))

    exact = 0
    close = 0          # 忽略 schwa/重音细节的近似匹配
    ok_count = 0
    errs = []
    by_len = {}

    for w, ph in sample:
        gold = lex_to_ipa(ph)
        pred, ok = g2p(w)
        if ok:
            ok_count += 1
        L = min(len(w), 10)
        b = by_len.setdefault(L, [0, 0])
        b[1] += 1
        if pred == gold:
            exact += 1
            b[0] += 1
        else:
            # 近似：去掉 schwa 与重复符号后比较
            norm = lambda s: s.replace("ə", "").replace("°", "")
            if norm(pred) == norm(gold):
                close += 1
            if len(errs) < 400:
                errs.append((w, gold, pred))

    total = len(sample)
    acc = exact / total if total else 0
    acc2 = (exact + close) / total if total else 0

    stats = {
        "sample": total,
        "exact_match": exact,
        "exact_rate": round(acc, 4),
        "near_match": close,
        "near_rate": round(acc2, 4),
        "g2p_converged": ok_count,
        "g2p_converged_rate": round(ok_count / total, 4) if total else 0,
        "by_word_length": {str(k): {"match": v[0], "total": v[1],
                                    "rate": round(v[0] / v[1], 4) if v[1] else 0}
                           for k, v in sorted(by_len.items())},
    }

    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=2))
    with io.open(OUT_ERR, "w", encoding="utf-8") as f:
        f.write("词\tLexique标准\tG2P预测\n")
        for w, g, p in errs:
            f.write("%s\t%s\t%s\n" % (w, g, p))

    sys.stderr.write("\n精确匹配 %.1f%%　近似匹配 %.1f%%　规则可收敛 %.1f%%\n"
                     % (acc * 100, acc2 * 100, ok_count / total * 100))
    sys.stderr.write("按词长：\n")
    for L, (m, t) in sorted(by_len.items()):
        sys.stderr.write("  长度 %2d：%5.1f%%（%d/%d）\n" % (L, 100 * m / t, m, t))

    verdict = ("可用作第二来源" if acc >= 0.95 else
               "仅可作人工核对候选，不得直接进成品" if acc >= 0.80 else
               "不可用：准确率不足，用了等于编造")
    sys.stderr.write("\n判定：%s\n" % verdict)
    stats["verdict"] = verdict
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()