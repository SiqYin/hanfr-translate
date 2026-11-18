#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""open_o_style.py — 音标第三批调整（最终口径）

用户最终要求（2026-11-18）：
    o → o̝   （U+006F + U+031D COMBINING UP TACK BELOW）
    e → e̝   （U+0065 + U+031D）

明确**不做**的：
    ɔ 不动（上一轮要求改 o，现已作废）
    鼻化元音 õ / ɒ̃ / ã 全部不动
    ɛ / œ / ø 等其余元音不动

为什么不能简单字符串替换：
  õ 是预组合字符 U+00F5，NFD 后是 o + U+0303。
  如果在 NFD 状态下替换 'o'，就会把鼻化元音拆坏。
  所以：
    1. 只在 NFC 状态下处理（õ 保持为一个字符 U+00F5，不碰）
    2. 替换时显式检查后一个字符不是 U+0303（防分解残留）
    3. 已经带 U+031D 的不重复加

用在三处生成流程：词库、音标词典、例句音标。
"""
import unicodedata

U_O = "o"
U_E = "e"
U_RAISED = "\u031d"     # COMBINING UP TACK BELOW
U_TILDE = "\u0303"      # COMBINING TILDE（鼻化）
U_OPEN_O = "\u0254"     # ɔ —— 本轮保持原样

# 预组合鼻化元音：整体保护，绝不拆开
NASAL_PRECOMPOSED = ["\u00f5", "\u00e3"]      # õ  ã
# 其他预组合元音（含鼻化符的近亲）也一并保护
OTHER_ACCENTS = ["\u1ebd", "\u0113", "\u00e9", "\u00e8", "\u00ea", "\u00eb",
                 "\u1ebf", "\u1ec1", "\u1ec3", "\u1ec5", "\u1ec7"]


def convert(s):
    """把 o→o̝、e→e̝。ɔ 与鼻化元音不变。"""
    if not s:
        return s

    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""

        if ch in (U_O, U_E):
            # 已经是带下加符的形式，不重复
            if nxt == U_RAISED:
                out.append(ch)
                i += 1
                continue
            # 后面是鼻化符 -> 属鼻化元音的分解形式，不动
            if nxt == U_TILDE:
                out.append(ch)
                i += 1
                continue
            out.append(ch + U_RAISED)
            i += 1
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def convert_keep_nasal(s):
    """保守版：先保护所有预组合字符，再转换，最后还原。"""
    if not s:
        return s
    protect = {}
    tmp = s
    targets = NASAL_PRECOMPOSED + OTHER_ACCENTS
    for k, ch in enumerate(targets):
        if ch in tmp:
            ph = "\uE000%02d\uE001" % k
            protect[ph] = ch
            tmp = tmp.replace(ch, ph)
    tmp = convert(tmp)
    for ph, ch in protect.items():
        tmp = tmp.replace(ph, ch)
    return tmp


if __name__ == "__main__":
    tests = [
        ("bɔn", "bɔn", "ɔ 不动"),
        ("bõ", "bõ", "鼻化 õ 不动"),
        ("pɔʁ", "pɔʁ", "port：ɔ 不动"),
        ("mɔ̃", "mɔ̃", "鼻化 ɔ̃ 不动"),
        ("o", "o\u031d", "单独的 o -> o̝"),
        ("e", "e\u031d", "单独的 e -> e̝"),
        ("do", "do\u031d", "dos"),
        ("le", "le\u031d", "le"),
        ("tʁɛ", "tʁɛ", "ɛ 不动"),
        ("fɛʁ", "fɛʁ", "faire：ɛ 不动"),
        ("bã", "bã", "鼻化 ã 不动"),
        ("tɒ̃", "tɒ̃", "鼻化 ɒ̃ 不动"),
        ("paʁle", "paʁle\u031d", "parler：词末 e 要改"),
        ("bõtø", "bõtø", "õ 与 ø 都不动"),
        ("bo", "bo\u031d", "beau"),
    ]
    print("转换自测（o→o̝ / e→e̝，ɔ 与鼻化元音均不动）：")
    ok = 0
    for src, exp, desc in tests:
        got = convert_keep_nasal(src)
        flag = "✓" if got == exp else "✗"
        if got == exp:
            ok += 1
        print("  %s %-10s -> %-10s %s" % (flag, src, got, desc))
    print("\n%d/%d 通过" % (ok, len(tests)))
