#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nasal_style.py — 法語鼻化元音標記體系的轉換

背景：
  法語鼻化元音有兩套標記。

  【传统标法（20 世纪初定型，现通行）】
      /ɛ̃/  pain, vin, fin
      /œ̃/  un, brun
      /ɑ̃/  temps, dans, grand
      /ɔ̃/  bon, maison, pont
    问题：/ɛ̃/ 与 /œ̃/ 在巴黎法语里已经合并成同一个音；
          /ɑ̃/ 实际读的不是后低元音 /ɑ/，而是介于 [ɒ] 与 [ɔ] 之间。

  【真实发音标法（本项目采用）】
      /ɛ̃/ 与 /œ̃/  →  /ã/   （两者已合并，用 a 记实际音值）
      /ɑ̃/          →  /ɒ̃/  （实际是圆唇后元音，非 /ɑ/）
      /ɔ̃/          →  /õ/   （实际音值更接近 o）

  依据：巴黎法语的实际音值。用户明确要求按真实发音走。

注意：
  这是**正字法层面的映射**，不是简单的字符串替换——
  /ɑ̃/ 与 /ɔ̃/ 都含鼻化符 U+0303，要先按「基字符 + 组合符」配对再替换，
  否则会把 /ɑ/ 错换成 /ɒ/ 却留下错位的鼻化符。
"""
import io
import json
import os
import re
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NASAL_TILDE = "\u0303"

# 旧 -> 新（按「基字符」映射，鼻化符保持不变位置）
BASE_MAP = {
    "ɛ": "a",   # ɛ̃ -> ã
    "œ": "a",   # œ̃ -> ã
    "ɑ": "ɒ",   # ɑ̃ -> ɒ̃
    "ɔ": "o",   # ɔ̃ -> õ
}

# 只处理这四个基字符 + 鼻化符的组合
TARGETS = ("ɛ", "œ", "ɑ", "ɔ")


def convert_nasals(s):
    """把旧体系的鼻化元音转成真实发音体系。

    逐字符扫描：遇到 ɛ/œ/ɑ/ɔ 且紧跟 U+0303 时，替换基字符。
    其余字符原样保留。
    """
    if not s:
        return s
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if ch in TARGETS and nxt == NASAL_TILDE:
            out.append(BASE_MAP[ch])
            out.append(NASAL_TILDE)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def convert_nfc(s):
    """先 NFC 再转换。

    有些數據源把 ɛ̃ 存成「ɛ + 组合鼻化符」，有些存成预组合字符。
    统一成 NFD 形式便于逐字符处理，转换后再 NFC 回来。
    """
    if not s:
        return s
    # NFC 归一，保证 ɛ̃ 是 ɛ + U+0303 两个码位
    x = unicodedata.normalize("NFC", s)
    x = convert_nasals(x)
    return unicodedata.normalize("NFC", x)


def stats(s):
    """统计各类鼻化元音出现次数，用于校验。"""
    import collections
    c = collections.Counter()
    i = 0
    while i < len(s) - 1:
        if s[i + 1] == NASAL_TILDE:
            c[s[i]] += 1
        i += 1
    return c


if __name__ == "__main__":
    tests = [
        ("pɛ̃", "pã"),          # pain
        ("bʁœ̃", "bʁã"),        # brun
        ("tɑ̃", "tɒ̃"),          # temps
        ("bɔ̃", "bõ"),           # bon
        ("mɛzɔ̃", "mɛzõ"),       # maison
        ("ʃjɛ̃", "ʃjã"),         # chien
        ("mɔ̃taɲ", "mõtaɲ"),     # montagne
        ("a", "a"),             # 无鼻化：不变
        ("ɛ", "ɛ"),             # 单独 ɛ（无鼻化）：不变
        ("bɔn", "bɔn"),         # bonne 里的 ɔ 不鼻化：不变
    ]
    print("转换自测：")
    ok = 0
    for src, exp in tests:
        got = convert_nfc(src)
        flag = "✓" if got == exp else "✗"
        if got == exp:
            ok += 1
        print("  %s %-12s -> %-12s 期望 %-12s" % (flag, src, got, exp))
    print("\n%d/%d 通过" % (ok, len(tests)))
