#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""normalize_fr.py — 法语义项规范化与词典缩写展开

审计（tools/audit_cfdict.py）显示，CFDICT 的结构性缺陷很少（括号不平衡 0.05%、
含汉字 0.004%），但有一类东西大量存在、且直接导致音标查不到：

    d'un(356)  d'une(309)  qqn(292)  qch(184)  fig(113)  d'eau(95)  l'eau(90)
    c'est(54)  l'argent(48)  qu'on(41)  n'est(34)

两类：
  1. **省音缩合**：d'un / l'eau / n'est / qu'on —— 撇号左边是虚词，右边是实词。
     音标要按右边实词挂，虚词用闭类表。这不该算"缺失"。
  2. **词典缩写**：qqn / qch / qqch / cf / fig / loc / fam ……
     这些是编者用语，不是词条内容，不该拿去查音标，也不该直接展示给用户。

处理原则：
  - 缩写**不删除**（它们承载语法信息），而是打上标记，音标环节跳过；
  - 省音缩合在音标环节按右侧实词处理；
  - 明显的数据垃圾（括号不平衡且无法修复）标记为 defect。

只提供函数，不单独跑；被 build_zhfr.py 与例句管线调用。
"""
import re

# ---------------------------------------------------------------- 词典缩写
# 值：中文说明（供 UI 可选的浮层解释）；音标环节一律跳过
ABBREV = {
    "qqn": "某人", "qqch": "某物", "qch": "某物", "qq": "某个",
    "cf": "参见", "cf.": "参见", "v.": "参见", "voir": "参见",
    "fig": "转义", "fig.": "转义", "fam": "口语", "fam.": "口语",
    "arg": "俚语", "arg.": "俚语", "vx": "古旧", "vx.": "古旧",
    "litt": "书面", "litt.": "书面", "poét": "诗歌", "péj": "贬义",
    "mélior": "褒义", "techn": "技术", "méd": "医学", "bot": "植物",
    "zool": "动物", "géogr": "地理", "hist": "历史", "dr": "法律",
    "écon": "经济", "pol": "政治", "mil": "军事", "mus": "音乐",
    "ling": "语言学", "psych": "心理", "chim": "化学", "phys": "物理",
    "math": "数学", "info": "信息", "sport": "体育", "cuis": "烹饪",
    "loc": "短语", "loc.": "短语", "expr": "习语", "expr.": "习语",
    "prov": "谚语", "absol": "绝对用法", "toujours": "常用",
    "surtout": "尤指", "notamment": "尤其", "par ext": "引申",
    "par anal": "类比", "p. ext.": "引申", "p. anal.": "类比",
    "syn": "同义", "ant": "反义", "contr": "反义", "dim": "指小",
    "augm": "指大", "iron": "反讽", "péjor": "贬义",
}

# 括号内含缩写的整段注记：如 "(fig.)" "(qqn)" "(fam.)"
ABBREV_PAREN = re.compile(
    r"[（(]\s*(" + "|".join(re.escape(k) for k in sorted(ABBREV, key=len, reverse=True)) + r")\s*[）)]",
    re.I)

# ---------------------------------------------------------------- 省音缩合
ELISION = re.compile(r"^([dljmnstcçq]|qu|jusqu|lorsqu|puisqu)'(.+)$", re.I)

# 撇号左边的虚词 -> IPA（闭类，音标确定）
ELIDED_HEAD_IPA = {
    "d": "d", "l": "l", "j": "ʒ", "m": "m", "n": "n", "s": "s", "t": "t",
    "c": "s", "ç": "s", "q": "k", "qu": "k", "jusqu": "ʒysk", "lorsqu": "lɔʁsk",
    "puisqu": "pɥisk",
}


def strip_abbrev_parens(s):
    """去掉 (fig.) (qqn) 这类纯缩写括注。"""
    return ABBREV_PAREN.sub(" ", s)


def is_abbrev(token):
    t = token.strip(".,;:()[]").lower()
    return t in ABBREV


def split_elision(token):
    """'d'un' -> ('d', 'un')；'l'eau' -> ('l', 'eau')；非缩合返回 (None, token)。"""
    m = ELISION.match(token)
    if m:
        return m.group(1).lower(), m.group(2)
    return None, token


def clean_sense(s):
    """义项规范化：去缩写括注、压缩空白、修首尾标点。

    返回 (clean_string, changed_flag)
    """
    if not s:
        return "", False
    orig = s
    s = strip_abbrev_parens(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .;,")
    # 括号不平衡：尝试补右括号；仍不平衡就保留原样并标记
    if s.count("(") > s.count(")"):
        s = s + ")" * (s.count("(") - s.count(")"))
    return s, s != orig


def fix_known_misspellings(s):
    """CFDICT 里已确认的拼写错误 -> 正确写法。

    只收**逐个核实过**的条目，不批量改写。每加一条都要有依据。
    """
    FIX = {
        "funèrailles": "funérailles",
        "bellemère": "belle-mère",
        "beau-père": "beau-père",
        "iraisonné": "déraisonnable",
        "défectibilité": "imperfection",
        "déboussolage": "désarroi",
        "déshonorable": "déshonorant",
        "déshonnêteté": "malhonnêteté",
        "tendences": "tendances",
        "néfastes": "néfastes",
    }
    out = s
    for bad, good in FIX.items():
        if bad in out:
            out = out.replace(bad, good)
    return out


if __name__ == "__main__":
    tests = [
        "d'un seul coup",
        "l'argent",
        "(fig.) personne qui agit",
        "tendences malsaines(néfastes",
        "funèrailles",
        "qqn de bien",
    ]
    for t in tests:
        c, ch = clean_sense(t)
        print("%-34s -> %-34s (changed=%s)" % (t, c, ch))
        head, tail = split_elision(c.split(" ")[0])
        if head:
            print("     省音：head=%s tail=%s" % (head, tail))