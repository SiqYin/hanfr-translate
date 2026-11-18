#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_ipa_dict.py — 生成前端可直接查的音标词典 app/ipa.js

需求：输入法语单词或整句，直接给出音标；句子还要带联诵。

为什么不能只靠词库里的 58,358 条：
  用户可能查任何法语词（词典未收录的也算），也可能贴一整句进来。
  所以需要一份**独立的、覆盖 Lexique383 全部 12.5 万词形**的音标词典。

体积权衡：
  全量 JSON 约 3.0 MB，gzip 后约 700 KB。汉南的 zhvi.js 是 26 MB，
  这个体积完全可以接受，换来「任何法语词都能查音标」。

输出：
  app/ipa.js   window.IPA = {"maison":"mɛzɔ̃", ...}

    python tools/build_ipa_dict.py
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nasal_style import convert_nfc          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
PHON_MAP = os.path.join(ROOT, "data", "lexique_phon_map.json")
OUT = os.path.join(ROOT, "app", "ipa.js")

# 闭类词：Lexique 未必收录单字形式，但这些读音无争议
CLOSED = {
    "le": "lə", "la": "la", "les": "le", "un": "œ̃", "une": "yn",
    "des": "de", "du": "dy", "de": "də", "au": "o", "aux": "o",
    "à": "a", "et": "e", "ou": "u", "où": "u", "en": "ɑ̃", "y": "i",
    "ne": "nə", "se": "sə", "ce": "sə", "que": "kə", "qui": "ki",
    "quoi": "kwa", "dont": "dɔ̃", "je": "ʒə", "tu": "ty", "nous": "nu",
    "vous": "vu", "il": "il", "elle": "ɛl", "ils": "il", "elles": "ɛl",
    "on": "ɔ̃", "me": "mə", "te": "tə", "lui": "lɥi", "leur": "lœʁ",
    "mon": "mɔ̃", "ma": "ma", "mes": "me", "ton": "tɔ̃", "ta": "ta",
    "tes": "te", "son": "sɔ̃", "sa": "sa", "ses": "se",
    "notre": "nɔtʁ", "votre": "vɔtʁ", "nos": "no", "vos": "vo",
    "est": "ɛ", "sont": "sɔ̃", "ont": "ɔ̃", "font": "fɔ̃",
    "très": "tʁɛ", "plus": "ply", "moins": "mwɛ̃", "tout": "tu",
}


def lex_to_ipa(code, pmap):
    out = []
    for c in code or "":
        v = pmap.get(c)
        if v is None:
            return None
        out.append(v)
    return "".join(out)


def main():
    pmap = json.load(io.open(PHON_MAP, encoding="utf-8"))
    rec = {}
    n_bad = 0

    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        i_o, i_p = hdr.index("ortho"), hdr.index("phon")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_p):
                continue
            o, ph = p[i_o].strip(), p[i_p].strip()
            if not o or not ph:
                continue
            k = o.lower()
            if k in rec:
                continue
            ipa = lex_to_ipa(ph, pmap)
            if not ipa:
                n_bad += 1
                continue
            # 鼻化元音改用真实发音标法（见 tools/nasal_style.py）
            rec[k] = convert_nfc(ipa)

    # 闭类词补齐
    for k, v in CLOSED.items():
        rec.setdefault(k, v)

    # 變體字母互補：Lexique 用 oe 拼法（coeur / oeuvre / soeur），
    # 但使用者會輸入 œ（cœur / œuvre / sœur）。兩邊都要能查到。
    #
    # 這是國際法語詞典的主流做法：œ 與 oe 等價、æ 與 ae 等價，
    # 再加上去變音符號（eleve 能命中 élève）。查詢時先折疊再查。
    import unicodedata

    def fold(s):
        s = s.replace("œ", "oe").replace("æ", "ae")
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.lower()

    # 折疊鍵 -> 所有原詞形（列表）。
    #
    # 為什麼要列表而不是單值：
    #   fold("élève") = fold("élevé") = fold("eleve") = "eleve"，
    #   但 élève（學生）與 élevé（被撫養的）是兩個不同詞，音標不同。
    #   只存一個會隨機丟掉另一個，使用者查 eleve 可能拿到 élevé 的音標。
    fold_map = {}
    for k in rec.keys():
        fk = fold(k)
        fold_map.setdefault(fk, [])
        if k not in fold_map[fk]:
            fold_map[fk].append(k)

    # 為 œ / æ 拼法補條目，讓使用者直接輸入 cœur 時能命中
    for k in list(rec.keys()):
        if "oe" in k:
            alt = k.replace("oe", "œ")
            if alt != k and alt not in rec:
                rec[alt] = rec[k]
        if "ae" in k:
            alt = k.replace("ae", "æ")
            if alt != k and alt not in rec:
                rec[alt] = rec[k]

    js = ("window.IPA=" + json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + ";\n"
          "window.IPA_FOLD=" + json.dumps(fold_map, ensure_ascii=False, separators=(",", ":")) + ";")
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    size = len(js.encode("utf-8"))
    print("詞形 %d 條（無法轉碼 %d），折疊鍵 %d" % (len(rec), n_bad, len(fold_map)))
    print("體積 %.2f MB -> %s" % (size / 1048576, OUT))
    for w in ("maison", "chien", "fleur", "nuit", "temps", "cœur", "œuvre",
              "élève", "eleve", "coeur", "sœur"):
        print("  %-10s %s" % (w, rec.get(w, "—— 缺")))


if __name__ == "__main__":
    main()