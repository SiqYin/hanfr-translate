#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fr2zh.py — 构建法→中反查层 app/fr2zh.js

照汉南 build_vi2zh.py 的三级结构：
  1. 功能词人工定稿表（data/fr_func_words.tsv）—— 虚词一律以人工为准
  2. Index-Translate 精排缓存（data/fr2zh_rank_cache.jsonl）—— 只排序，不生成
  3. 启发式兜底（义项位置靠前 > 二字词优先 > 词频）

输出：
  app/fr2zh.js   window.FR2ZH = {"<法语词>": ["<中文1>", "<中文2>"]}

    python tools/build_fr2zh.py
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
CACHE = os.path.join(ROOT, "data", "fr2zh_rank_cache.jsonl")
FUNC = os.path.join(ROOT, "data", "fr_func_words.tsv")
FREQ = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据", "Lexique383.tsv"))
OUT = os.path.join(ROOT, "app", "fr2zh.js")

MAX_GLOSS = 4
MAX_TOKENS = 4

CJK = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")


def load_zf():
    src = io.open(SRC, encoding="utf-8").read()
    m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
    return json.loads(m.group(1))


def norm_fr(s):
    """法语义项规范化：小写、去括注、去首尾标点。"""
    s = re.sub(r"[（(][^）)]*[）)]", " ", (s or "").lower())
    s = re.sub(r"[.,;:!?«»\"'…\[\]]+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def load_func():
    d = {}
    if os.path.exists(FUNC):
        for line in io.open(FUNC, encoding="utf-8"):
            if not line.strip() or line.startswith("#"):
                continue
            p = line.split("\t")
            if len(p) < 2:
                continue
            w = p[0].strip().lower()
            g = [x.strip() for x in p[1].split("；") if x.strip()]
            if w and g:
                d[w] = g
    return d


def load_cache():
    c = {}
    if os.path.exists(CACHE):
        for line in io.open(CACHE, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if isinstance(d.get("v"), list) and d.get("w") and d["v"]:
                c[d["w"]] = d["v"]
    return c


def load_freq():
    """法語詞頻：用於兜底排序（越高頻越可能是一般義）。"""
    f = {}
    if not os.path.exists(FREQ):
        return f
    with io.open(FREQ, encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        try:
            i_o = hdr.index("ortho")
            i_a = hdr.index("freqlemlivres")
            i_b = hdr.index("freqlemfilms2")
        except ValueError:
            return f
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_a, i_b):
                continue
            w = p[i_o].strip().lower()
            if not w:
                continue
            try:
                v = float(p[i_a] or 0) + float(p[i_b] or 0)
            except ValueError:
                v = 0.0
            if v > f.get(w, -1):
                f[w] = v
    return f


def load_zh_freq():
    """中文词频表：用於判斷候選中文詞「本身是否常用」。

    maison 反演出上百個候選（宇、屋、房、房子、住宅、家…），
    光看詞長會把「宇」「屋」這種單字推到前面——它們義項序是 0，但現代漢語
    已經不單獨成詞。必須用詞頻判斷這個中文詞本身是否常用。
    """
    path = os.path.join(ROOT, "data", "modern_chinese_words.tsv")
    if not os.path.exists(path):
        # 漢南歸檔裡有同一份表，借用
        alt = os.path.normpath(os.path.join(
            ROOT, "..", "..", "..", "2026-11-7 汉南辞典", "01_源码", "hanviet-app",
            "data", "modern_chinese_words.tsv"))
        path = alt if os.path.exists(alt) else path
    rank = {}
    if not os.path.exists(path):
        return rank
    with io.open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        try:
            i_w = header.index("词语")
            i_r = header.index("频序号")
        except ValueError:
            i_w, i_r = 0, 1
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_w, i_r):
                continue
            w = p[i_w].strip()
            if not w:
                continue
            try:
                r = int(p[i_r])
            except ValueError:
                r = 99999
            if w not in rank or r < rank[w]:
                rank[w] = r
    return rank


ZH_RANK = {}


def heur_rank(cands, freq):
    """啟發式排序。

    cands 的每項是 (中文詞, 義項序, 中文詞長)。

    權重是實測調出來的，每次調整都有對應的壞例子：
      1. **中文詞是否常用**（modern_chinese_words 詞頻序）—— 最強項。
         maison -> 宇/屋/房/房子：宇、屋義項序都是 0 且只有一字，
         但現代漢語不說「宇」表示房子。詞頻表能擋住這種。
         不在詞頻表裡的（生僻字、文言單字）重罰。
      2. 中文詞長度 —— 次要。短詞通常更基本。
      3. 義項序 —— 同詞條內越靠前越常用。
      4. 法語詞頻 —— 微調。
    """
    def key(c):
        zh, j, L = c
        r = ZH_RANK.get(zh)
        if r is None:
            s = 600.0                      # 不在常用詞表：幾乎排最後
        else:
            s = min(500.0, 40.0 * (r ** 0.35))
            # 「大」「犬」「錠」這類字頻次很高，但現代漢語已不能單獨成詞，
            # 它們主要作為構詞成分出現（大学/犬齿/锭剂）。單字候選要有懲罰，
            # 否則 médecin -> 「大」、pain -> 「錠」 這種荒謬結果會排第一。
            if L == 1:
                s += 70
        s += (L - 1) * 8                   # 長度：輕度偏好
        s += j * 6                         # 義項序
        s -= min(freq, 500) / 500.0 * 5    # 法語詞頻：微調
        return (s, L, j, zh)
    return [c[0] for c in sorted(cands, key=key)]


def main():
    global ZH_RANK
    ZF = load_zf()
    func = load_func()
    cache = load_cache()
    freqmap = load_freq()
    ZH_RANK = load_zh_freq()
    if ZH_RANK:
        sys.stderr.write("中文常用詞表 %d 條\n" % len(ZH_RANK))
    else:
        sys.stderr.write("警告：缺中文常用詞表，排序會退化\n")

    # 反演：法語詞（1-4 詞） -> {中文詞: (最小義項序, 中文詞長)}
    #
    # 記中文詞長是關鍵：eau 會同時從「水」「药水」「水溶液」反演出來，
    # 三者義項序都是 0（各詞條自己的首義），單靠義項序分不出主次。
    # 中文詞頭越短越基本（水 < 药水 < 水溶液），用長度做決勝。
    cand = collections.defaultdict(dict)
    for e in ZF:
        zh, senses = e[1], e[3]
        if not zh or not senses:
            continue
        for j, raw in enumerate(senses.split("；")):
            s = norm_fr(raw)
            if not s:
                continue
            s = re.sub(r"^(le|la|les|l'|un|une|des|du|d'|de)\s+", "", s)
            toks = [t for t in re.split(r"[\s,;:]+", s) if t]
            if not (1 <= len(toks) <= MAX_TOKENS):
                continue
            phrase = " ".join(toks)
            if not re.match(r"^[a-zà-ÿœæç' -]+$", phrase):
                continue
            prev = cand[phrase].get(zh)
            if prev is None or j < prev[0]:
                cand[phrase][zh] = (j, len(zh))

    sys.stderr.write("反演出 %d 個法語詞\n" % len(cand))

    out = {}
    n_func = n_ai = n_fb = 0
    for phrase, d in cand.items():
        if phrase in func:
            out[phrase] = func[phrase][:MAX_GLOSS]
            n_func += 1
            continue
        g = cache.get(phrase)
        if g:
            out[phrase] = g[:MAX_GLOSS]
            n_ai += 1
            continue
        cands = [(zh, j, L) for zh, (j, L) in d.items() if CJK.match(zh)]
        if not cands:
            cands = [(zh, j, L) for zh, (j, L) in d.items()]
        f0 = freqmap.get(phrase.split()[0], 0.0)
        out[phrase] = heur_rank(cands, f0)[:2]
        n_fb += 1

    # 功能詞表裡的詞即使不在候選池也要有條目
    for w, g in func.items():
        if w not in out:
            out[w] = g[:MAX_GLOSS]
            n_func += 1

    js = "window.FR2ZH=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    print("條目 %d（功能詞定稿 %d / AI 精排 %d / 啟發式 %d）"
          % (len(out), n_func, n_ai, n_fb))
    print("體積 %.2f MB -> %s" % (len(js.encode("utf-8")) / 1048576, OUT))

    # 自檢
    for w in ["eau", "livre", "être", "avoir", "de", "à", "faire", "maison"]:
        print("  %-10s %s" % (w, out.get(w, "—— 缺")))


if __name__ == "__main__":
    main()