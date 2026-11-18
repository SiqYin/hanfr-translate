#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g2p_fr.py — 规则式法语音标生成（Lexique 覆盖不到时的补充来源）

为什么不"让模型猜"：
  音标必须是可复核的。模型生成的音标无法验证，等于编造（红线 R5）。
  本模块用的是**确定性规则**：法语拼写→读音的对应关系在语言学上是高度规则的，
  规则从 Lexique383 的 12.5 万条 ortho/phon 对里统计出来，可靠且可审计。

定位：
  **第二来源，不是第一来源**。有 Lexique 音标时一律用 Lexique（实测数据优先）；
  只有 Lexique 查不到时（专业词、派生词、罕见词）才用规则推导。

输出每条都带 source 标记：
  lexique  — 来自 Lexique383（可信）
  g2p      — 规则推导（可用，但标注来源）
  pending  — 规则也无法确定（写 "?"，UI 标「待核」）

自测：
  python tools/g2p_fr.py
"""
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
PHON_MAP = os.path.join(ROOT, "data", "lexique_phon_map.json")

with io.open(PHON_MAP, encoding="utf-8") as f:
    _PM = json.load(f)


def lex_to_ipa(code):
    return "".join(_PM.get(c, "?") for c in (code or ""))


# ---------------------------------------------------------------- 规则表
# 顺序敏感：长串在前，短串在后。每条是 (正则, IPA, 说明)
# 覆盖法语音标的主要难点：鼻化元音、词末静音辅音、-er/-ez、开闭音节 e/ɛ、o/ɔ

VOWEL_NASAL = {
    "ain": "ɛ̃", "ein": "ɛ̃", "aim": "ɛ̃", "eim": "ɛ̃", "yn": "ɛ̃", "en": "ɑ̃",
    "am": "ɑ̃", "an": "ɑ̃", "em": "ɑ̃", "on": "ɔ̃", "om": "ɔ̃", "in": "ɛ̃",
    "im": "ɛ̃", "un": "œ̃", "um": "œ̃", "oin": "wɛ̃",
}

# 词尾常见组合（先于通用规则匹配）
WORD_END = [
    (r"eaux$", "o"),
    (r"aux$", "o"),
    (r"eau$", "o"),
    (r"aient$", "ɛ"),
    (r"ais$", "ɛ"), (r"ait$", "ɛ"), (r"aid$", "ɛ"),
    (r"er$", "e"), (r"ez$", "e"), (r"ée?$", "e"), (r"és$", "e"), (r"ées$", "e"),
    (r"tion$", "sjɔ̃"), (r"tions$", "sjɔ̃"),
    (r"eur$", "œʁ"), (r"eux$", "ø"), (r"euse$", "øz"),
    (r"ière$", "jɛʁ"), (r"ier$", "je"),
    (r"age$", "aʒ"), (r"ages$", "aʒ"),
    (r"té$", "te"), (r"tés$", "te"), (r"tié$", "tje"),
    (r"ance$", "ɑ̃s"), (r"ence$", "ɑ̃s"),
    (r"isme$", "ism"), (r"iste$", "ist"),
    (r"ment$", "mɑ̃"), (r"ments$", "mɑ̃"),
    (r"esse$", "ɛs"),
    (r"ine$", "in"), (r"ines$", "in"),
    (r"ique$", "ik"), (r"iques$", "ik"),
    (r"ure$", "yʁ"),
    (r"oir$", "waʁ"), (r"oire$", "waʁ"),
    (r"able$", "abl"), (r"ible$", "ibl"),
    (r"ôtre$", "otʁ"),
    (r"ail$", "aj"), (r"aille$", "aj"),
    (r"eil$", "ɛj"), (r"eille$", "ɛj"),
    (r"ouille$", "uj"),
]

# 词末静音辅音（法语最常见陷阱）
SILENT_FINAL = set("tdsxzp")

# 辅音组合
CONS = [
    ("tch", "tʃ"), ("sch", "ʃ"), ("ch", "ʃ"), ("ph", "f"), ("th", "t"),
    ("gn", "ɲ"), ("qu", "k"), ("gu", "ɡ"), ("ill", "ij"), ("ll", "l"),
    ("ss", "s"), ("mm", "m"), ("nn", "n"), ("tt", "t"), ("pp", "p"),
    ("rr", "ʁ"), ("cc", "k"), ("ff", "f"), ("bb", "b"), ("dd", "d"),
    ("gg", "ɡ"), ("xl", "ksl"),
]

SINGLE_CONS = {
    "b": "b", "c": "k", "ç": "s", "d": "d", "f": "f", "g": "ɡ", "h": "",
    "j": "ʒ", "k": "k", "l": "l", "m": "m", "n": "n", "p": "p", "q": "k",
    "r": "ʁ", "s": "s", "t": "t", "v": "v", "w": "w", "x": "ks", "z": "z",
}

VOWELS = {
    "a": "a", "â": "ɑ", "à": "a", "e": "ə", "é": "e", "è": "ɛ", "ê": "ɛ",
    "ë": "ɛ", "i": "i", "î": "i", "ï": "i", "o": "o", "ô": "o", "ö": "ɔ",
    "u": "y", "ù": "y", "û": "y", "ü": "y", "y": "i", "œ": "œ", "æ": "e",
}


def g2p(word):
    """规则式法语音标。返回 (ipa, ok)。ok=False 表示有无法确定的部分。"""
    w = word.strip().lower()
    if not w or not re.match(r"^[a-zà-ÿœæç'-]+$", w):
        return "", False

    # 连字符复合词：逐段转换再拼接
    if "-" in w:
        parts = [p for p in w.split("-") if p]
        out, allok = [], True
        for p in parts:
            ip, ok = g2p(p) if len(p) > 1 else (SINGLE_CONS.get(p, VOWELS.get(p, "")), True)
            out.append(ip)
            allok = allok and ok
        return "-".join(out), allok

    ok = True
    out = []
    i, n = 0, len(w)

    while i < n:
        matched = False

        # 1) 词尾固定组合（只在剩余部分等于该模式时生效）
        rest = w[i:]
        for pat, ip in WORD_END:
            if re.fullmatch(pat, rest):
                out.append(ip)
                i = n
                matched = True
                break
        if matched:
            break

        # 2) 鼻化元音
        for g, ip in VOWEL_NASAL.items():
            if rest.startswith(g):
                # 鼻化后若紧跟元音或 n/m 重复（bonne/bonnement），不鼻化
                after = w[i + len(g):i + len(g) + 1]
                if after and after in "aeiouéèêàâôîûy":
                    continue
                if len(g) >= 2 and i + len(g) < n and w[i + len(g)] == g[-1]:
                    continue
                out.append(ip)
                i += len(g)
                matched = True
                break
        if matched:
            continue

        # 3) 辅音组合
        for g, ip in CONS:
            if rest.startswith(g):
                out.append(ip)
                i += len(g)
                matched = True
                break
        if matched:
            continue

        # 4) 元音组合
        two = rest[:2]
        if two == "ou":
            out.append("u"); i += 2; continue
        if two == "oi":
            out.append("wa"); i += 2; continue
        if two == "au":
            out.append("o"); i += 2; continue
        if two in ("ai", "aî"):
            out.append("ɛ"); i += 2; continue
        if two == "ei":
            out.append("ɛ"); i += 2; continue
        if two == "eu":
            out.append("ø"); i += 2; continue
        if two == "œu":
            out.append("œ"); i += 3; continue
        if two == "ui":
            out.append("ɥi"); i += 2; continue
        if two == "ie":
            out.append("i"); i += 2; continue

        ch = w[i]

        # 5) 词末静音辅音
        if i == n - 1 and ch in SILENT_FINAL:
            # 单音节实词里 -t/-s 有时发音，这里保守静音
            i += 1
            continue
        if i == n - 1 and ch == "e":
            i += 1          # 词尾 e 不发音
            continue
        if i == n - 1 and ch == "h":
            i += 1
            continue

        # 6) c / g 的软硬
        if ch == "c":
            nxt = w[i + 1] if i + 1 < n else ""
            out.append("s" if nxt in "eéèêiîy" else "k")
            i += 1
            continue
        if ch == "g":
            nxt = w[i + 1] if i + 1 < n else ""
            out.append("ʒ" if nxt in "eéèêiîy" else "ɡ")
            i += 1
            continue
        if ch == "s":
            # 元音之间的 s 浊化为 z
            prev = w[i - 1] if i > 0 else ""
            nxt = w[i + 1] if i + 1 < n else ""
            if prev and prev in "aeiouéèêàâôîûyœæ" and nxt and nxt in "aeiouéèêàâôîûyœæ":
                out.append("z")
            else:
                out.append("s")
            i += 1
            continue

        # 7) 半元音：i/u 在元音前
        if ch in "iu" and i + 1 < n and w[i + 1] in "aeiouéèêàâôîûy":
            out.append("j" if ch == "i" else "ɥ")
            i += 1
            continue

        # 8) 普通元音 / 辅音
        if ch in VOWELS:
            out.append(VOWELS[ch])
            i += 1
            continue
        if ch in SINGLE_CONS:
            v = SINGLE_CONS[ch]
            if v:
                out.append(v)
            i += 1
            continue

        # 9) 未覆盖字符
        ok = False
        out.append("?")
        i += 1

    ipa = "".join(out)
    # 连续的 schwa 合并、去重音痕迹
    ipa = re.sub(r"ə+", "ə", ipa)
    return ipa, ok and "?" not in ipa


# ---------------------------------------------------------------- 自测
SELFTEST = {
    "eau": "o", "maison": "mɛzɔ̃", "chien": "ʃjɛ̃", "temps": "tɑ̃",
    "fleur": "flœʁ", "nuit": "nɥi", "parler": "paʁle", "montagne": "mɔ̃taɲ",
    "beauté": "bote", "maison": "mɛzɔ̃", "nation": "nasjɔ̃",
    "chanteur": "ʃɑ̃tœʁ", "heureux": "œʁø", "première": "pʁəmjɛʁ",
    "fromage": "fʁɔmaʒ", "santé": "sɑ̃te", "musique": "myzik",
    "ouvrier": "uvʁije", "cheval": "ʃəval", "jour": "ʒuʁ",
}

if __name__ == "__main__":
    sys.stderr.write("规则式 G2P 自测：\n")
    good = 0
    for w, exp in SELFTEST.items():
        got, ok = g2p(w)
        flag = "✓" if got == exp else "✗"
        if got == exp:
            good += 1
        sys.stderr.write("  %s %-12s %-12s 期望 %-12s\n" % (flag, w, got, exp))
    sys.stderr.write("\n%d/%d 通过\n" % (good, len(SELFTEST)))