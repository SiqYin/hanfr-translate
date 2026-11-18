#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_form_index.py — 构建「变位形式 -> 原型 + 变位说明」索引

用户需求：搜一个词的变位形式（如 mangeais），要能
  1. 查出原型（manger）
  2. 直接显示当前是什么变位形式（imparfait 1s/2s）

数据来源：app/conj.js（上一步生成的变位表）
输出：app/form_index.js   window.FORMIDX = {"mangeais": [["manger","imparfait","1s/2s"]], ...}

同一形式可能对应多个原型（如 "parle" 既是 parler 的现在时，也可能是名词），
所以值是数组。

    python tools/build_form_index.py
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
SRC = os.path.join(ROOT, "app", "conj.js")
OUT = os.path.join(ROOT, "app", "form_index.js")

# 人称标签（给前端显示用）
PERSON_ZH = {
    "1s": "第一人称单数", "2s": "第二人称单数", "3s": "第三人称单数",
    "1p": "第一人称复数", "2p": "第二人称复数", "3p": "第三人称复数",
}
TENSE_ZH = {
    "présent": "现在时", "imparfait": "未完成过去时", "passé simple": "简单过去时",
    "futur": "简单将来时", "conditionnel": "条件式现在时",
    "subjonctif": "虚拟式现在时", "impératif": "命令式",
}
PERSONS = ["1s", "2s", "3s", "1p", "2p", "3p"]
IMP_PERSONS = ["2s", "1p", "2p"]


def main():
    src = io.open(SRC, encoding="utf-8").read()
    m = re.search(r"window\.CONJ=(\{.*\});\s*$", src, re.S)
    if not m:
        sys.stderr.write("无法解析 conj.js\n")
        raise SystemExit(1)
    CONJ = json.loads(m.group(1))
    sys.stderr.write("变位表 %d 个动词\n" % len(CONJ))

    # form -> [(lemma, tense, person)]
    idx = collections.defaultdict(list)

    for lemma, table in CONJ.items():
        for tense in TENSE_ZH:
            forms = table.get(tense) or []
            if not forms:
                continue
            persons = IMP_PERSONS if tense == "impératif" else PERSONS
            for i, f in enumerate(forms):
                if not f:
                    continue
                p = persons[i] if i < len(persons) else ""
                idx[f].append([lemma, tense, p])

        # 非人称形式
        for key, label in (("_infinitif", "不定式"),
                           ("_participe présent", "现在分词"),
                           ("_participe passé", "过去分词")):
            v = table.get(key)
            if v:
                idx[v].append([lemma, label, ""])
                # 过去分词要补性数变化：allé -> allée/allés/allées
                # 用户会搜 "allés"（复数），不补就查不到
                if key == "_participe passé" and not v.endswith("s"):
                    if v.endswith("é") or v.endswith("i") or v.endswith("u") \
                            or v.endswith("t") or v.endswith("s"):
                        idx[v + "e"].append([lemma, label, "f.s"])
                        idx[v + "s"].append([lemma, label, "m.p"])
                        idx[v + "es"].append([lemma, label, "f.p"])

    # 去重 + 排序（同一原型的多个人称合并）
    out = {}
    for form, items in idx.items():
        # 同一 (lemma, tense) 的多个人称合并成 "1s/2s"
        merged = collections.OrderedDict()
        for lemma, tense, p in items:
            k = (lemma, tense)
            if k not in merged:
                merged[k] = []
            if p and p not in merged[k]:
                merged[k].append(p)
        lst = []
        for (lemma, tense), ps in merged.items():
            lst.append([lemma, tense, "/".join(ps)])
        # 短原型优先（更像原形），再按 tense 排序
        lst.sort(key=lambda x: (len(x[0]), x[0], x[1]))
        out[form] = lst

    js = "window.FORMIDX=" + json.dumps(out, ensure_ascii=False,
                                        separators=(",", ":")) + ";"
    js += "\nwindow.CONJ_TENSE_ZH=" + json.dumps(TENSE_ZH, ensure_ascii=False,
                                                 separators=(",", ":")) + ";"
    js += "\nwindow.CONJ_PERSON_ZH=" + json.dumps(PERSON_ZH, ensure_ascii=False,
                                                  separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    size = len(js.encode("utf-8"))
    print("形式索引 %d 条 -> %s（%.2f MB）" % (len(out), OUT, size / 1048576))

    # 自检
    for w in ("mangeais", "suis", "allés", "irai", "parlé", "fini"):
        if w in out:
            print("  %-10s -> %s" % (w, out[w][:2]))
        else:
            print("  %-10s 未收录" % w)


if __name__ == "__main__":
    main()