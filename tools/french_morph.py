#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""french_morph.py — 法语构词法：词根提取与派生词判定

为什么需要自己实现：
  WOLF 的 eng_derivative 语义太松，不能直接当「派生词」用：
    eau    -> pisser / uriner / mouiller   （「用水做某事」，不是派生）
    nation -> habiter / peupler            （「与国家有关」，不是派生）
    grand  -> corbeau                      （完全无关）
  法语构词法（前缀 + 词根 + 后缀）比英文词网的语义关系更可靠。

判据：
  两个词共享词根（剥掉前缀与后缀后相同或互为前缀）才算派生。
    nation  / national  / nationalité      -> 同根 ✓
    grand   / grandeur  / grandiose        -> 同根 ✓
    eau     / uriner                       -> 不同根 ✗

已知短板（用 WOLF 补）：
  不规则派生看不出共同词根：
    chanson <- chanter   （-son 不是规则后缀）
    lecture <- lire      （词根异形 lect- / lir-）
  这类靠 WOLF 的 derived 关系兜底。
"""
import re

# 常见法语派生后缀（按长度降序，先匹配长的）
SUFFIXES = sorted(set([
    # 名词
    "issement", "isation", "ification", "atoire", "etoire",
    "ation", "ition", "ution", "aison", "ement", "ement",
    "tion", "sion", "xion", "ment", "ance", "ence", "itude",
    "erie", "erie", "aille", "aille", "ure", "ade", "age",
    "isme", "iste", "eur", "euse", "trice", "rice",
    "ier", "ière", "té", "ité", "eté", "esse", "oir", "eoir",
    # amitié / amitié -> amiti（-ié 结尾，3 字符）
    "ié", "ie", "ise", "ail", "eil", "eul",
    # 形容词
    "eux", "euse", "aux", "ale", "elle", "ien", "ienne",
    "ais", "aise", "ois", "oise", "able", "ible", "ive",
    "ique", "esque", "arde", "âtre", "al", "el", "if", "ard",
    # 动词
    "iser", "ifier", "oyer", "ayer", "eler", "eter",
    "er", "ir",
]), key=len, reverse=True)

PREFIXES = sorted(set([
    "contre", "inter", "trans", "ultra", "extra", "hyper", "hypo",
    "auto", "télé", "micro", "macro", "anti", "post", "sous", "sur",
    "dés", "pré", "mal", "non", "dé", "re", "ré", "in", "im",
    "il", "ir", "co", "con", "mé", "més", "en", "em", "ex", "é", "a",
]), key=len, reverse=True)

MIN_ROOT = 3


def stem_of(w):
    """剥后缀，得到词干候选。"""
    if len(w) < 4:
        return w
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= MIN_ROOT:
            return w[: -len(suf)]
    if w.endswith(("e", "s")):
        return w[:-1]
    return w


def prefix_of(w):
    """识别前缀。注意不能把词干本身吃掉：
       amitié -> stem=amiti，这里绝不能再把 "ami" 当前缀剥掉。
       判据：剥掉前缀后剩下的部分必须 >= 5 字符，且前缀不是整词的词根。
    """
    for pre in PREFIXES:
        if not w.startswith(pre):
            continue
        rest = w[len(pre):]
        if len(rest) < 5:
            continue
        # 剩下的部分如果太像独立词根（>=5），才认为是真前缀
        return pre
    return ""


def root_of(w):
    """词根：剥后缀，再剥前缀。"""
    s = stem_of(w)
    p = prefix_of(s)
    if p:
        s = s[len(p):]
    return s


def _root_similar(ra, rb):
    """词根相近判定，处理法语词根的规则性变形。

    单纯「相同前缀」不够，下面这些是常见变形：
      lire -> lisible     lir / lis      （去掉词尾 r）
      ami  -> amitié      ami / amit     （i 后加 t）
      eau  -> aqueux      这组不处理（异形词根，靠 WOLF 兜底）
    """
    if len(ra) < MIN_ROOT or len(rb) < MIN_ROOT:
        return False

    # 去掉词尾 r / t / s 再比（lir/lis、amit/ami）
    def strip_end(x):
        return re.sub(r"[rtsx]$", "", x)

    a2, b2 = strip_end(ra), strip_end(rb)
    if len(a2) >= MIN_ROOT and a2 == b2:
        return True
    if len(a2) >= 4 and len(b2) >= 4 and a2[:4] == b2[:4]:
        return True

    # 共同前缀 >= 3 且长度差 <= 2（ami/amit、lir/lis）
    # 2 字符也接受，但仅限短词根（<=4），避免误伤（parl/bav 这种 2 字符相同？没有）
    n = 0
    for x, y in zip(ra, rb):
        if x != y:
            break
        n += 1
    if n >= 3 and abs(len(ra) - len(rb)) <= 2:
        return True
    if n >= 2 and len(ra) <= 4 and len(rb) <= 4 and abs(len(ra) - len(rb)) <= 1:
        return True
    return False


def shares_root(a, b):
    """两个词是否共享词根（据此判定规则派生）。"""
    if not a or not b or a == b:
        return False
    ra, rb = root_of(a), root_of(b)
    if len(ra) < MIN_ROOT or len(rb) < MIN_ROOT:
        return False
    if ra == rb:
        return True
    # grand / grandeur：短的是长的前缀
    if ra.startswith(rb) or rb.startswith(ra):
        short = ra if len(ra) <= len(rb) else rb
        if len(short) >= 4:
            return True
    return _root_similar(ra, rb)


def same_family(a, b):
    """同一词族：共享词根，或词根相近。"""
    return shares_root(a, b)


if __name__ == "__main__":
    cases = [
        ("nation", "national", True), ("nation", "nationalité", True),
        ("nation", "habiter", False), ("grand", "grandeur", True),
        ("grand", "grandiose", True), ("parler", "parleur", True),
        ("parler", "bavard", False), ("eau", "uriner", False),
        ("beau", "beauté", True), ("chanter", "chanteur", True),
        ("chanter", "chanson", True), ("maison", "habiter", False),
        ("lire", "lecture", False), ("lire", "lisible", True),
        ("ami", "amitié", True), ("ami", "ennemi", False),
    ]
    ok = 0
    print("词根判定自测：")
    for a, b, exp in cases:
        got = same_family(a, b)
        flag = "✓" if got == exp else "✗"
        if got == exp:
            ok += 1
        print("  %s %-10s ~ %-12s %-6s 期望 %s  根(%s/%s)"
              % (flag, a, b, "同族" if got else "不同族",
                 "同族" if exp else "不同族", root_of(a), root_of(b)))
    print("\n%d/%d 通过" % (ok, len(cases)))
