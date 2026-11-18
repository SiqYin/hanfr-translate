#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_zhfr.py — 构建中→法主词库 app/zhfr.js

严格照汉南 build_zhvi.py 的结构与流程，法语侧多挂一个 IPA 字段。

数据流：
  cedict.u8     中文词头 / 拼音 / 繁简 / 英文义项骨架
  cfdict.u8     中→法义项（主来源）
  Lexique383    法语词形 → IPA / 词性
  OpenCC        STCharacters / TSCharacters 繁简表

输出：
  app/zhfr.js              window.ZF = [[trad,simp,pinyin,senses,ipa,pos,example,meta], ...]
  data/zhfr_src.json       构建中间态（供后续管线与审计使用）
  data/zhfr_stats.json     统计快照
  data/zhfr_report.tsv     逐条构建报告（IPA 命中 / 缺失）

字段定义见 00_归档说明.md 第三节。

    python tools/build_zhfr.py
    python tools/build_zhfr.py --limit 5000    # 试跑
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_fr import (          # noqa: E402
    is_abbrev, split_elision, clean_sense as norm_sense,
    fix_known_misspellings,
)
from nasal_style import convert_nfc  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))

CEDICT = os.path.join(RAW, "cedict.u8")
CFDICT = os.path.join(RAW, "cfdict.u8")
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
PHON_MAP = os.path.join(ROOT, "data", "lexique_phon_map.json")
ST_CHARS = os.path.join(ROOT, "tools", "opencc", "STCharacters.txt")
TS_CHARS = os.path.join(ROOT, "tools", "opencc", "TSCharacters.txt")

OUT_JS = os.path.join(ROOT, "app", "zhfr.js")
OUT_SRC = os.path.join(ROOT, "data", "zhfr_src.json")
OUT_STATS = os.path.join(ROOT, "data", "zhfr_stats.json")
OUT_REPORT = os.path.join(ROOT, "data", "zhfr_report.tsv")

MAX_SENSES = 5          # 与汉南一致：最多 5 条义项
MAX_WORD_LEN = 8        # 词头长度上限（过滤异常长串）

# ---------------- 繁简 ----------------
def load_opencc(path):
    d = {}
    if not os.path.exists(path):
        return d
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("\t")
            if len(p) >= 2:
                d[p[0]] = p[1].split(" ")[0]
    return d


ST = load_opencc(ST_CHARS)      # 简 -> 繁
TS = load_opencc(TS_CHARS)      # 繁 -> 简


def to_trad(s):
    return "".join(ST.get(c, c) for c in s)


def to_simp(s):
    return "".join(TS.get(c, c) for c in s)


# ---------------- 拼音 ----------------
ACCENT = {"ā": "a", "á": "a", "ǎ": "a", "à": "a", "ē": "e", "é": "e", "ě": "e", "è": "e",
          "ī": "i", "í": "i", "ǐ": "i", "ì": "i", "ō": "o", "ó": "o", "ǒ": "o", "ò": "o",
          "ū": "u", "ú": "u", "ǔ": "u", "ù": "u", "ǖ": "ü", "ǘ": "ü", "ǚ": "ü", "ǜ": "ü",
          "ń": "n", "ň": "n", "ǹ": "n", "ḿ": "m"}
MARKS = {"a": "āáǎà", "o": "ōóǒò", "e": "ēéěè", "i": "īíǐì", "u": "ūúǔù", "ü": "ǖǘǚǜ"}


def syllable(py):
    """CEDICT 数字声调 -> 带调符号"""
    m = re.match(r"^([A-Za-zü:]+)([0-5])?$", py)
    if not m:
        return py
    body, tone = m.group(1).replace("u:", "ü").replace("v", "ü"), m.group(2)
    if not tone or tone in "50":
        return body
    t = int(tone) - 1
    low = body.lower()
    if "a" in low:
        idx = low.index("a")
    elif "e" in low:
        idx = low.index("e")
    elif "ou" in low:
        idx = low.index("o")
    else:
        vs = [i for i, c in enumerate(low) if c in "aeiouü"]
        if not vs:
            return body
        idx = vs[-1]
    return body[:idx] + MARKS[low[idx]][t] + body[idx + 1:]


def pinyin_display(py):
    out = " ".join(syllable(x) for x in py.split())
    out = re.sub(r"\s+r(?=$|\s)", "r", out)
    return out[:1].lower() + out[1:] if out else out


# ---------------- Lexique383：法语词 -> IPA / 词性 ----------------
# Lexique 的 phon 字段是 LAIPTTS 派生的单字符编码，不是 IPA：
#     maison -> "mEz§"    chien -> "Sj5"    temps -> "t@"
# 必须经 tools/derive_lexique_phon.py 反推出的映射表转成 IPA，否则渲染出来是乱码。
PHON_TO_IPA = {}
if os.path.exists(PHON_MAP):
    with io.open(PHON_MAP, encoding="utf-8") as f:
        PHON_TO_IPA = json.load(f)
else:
    sys.stderr.write("警告：缺少 %s，音标将无法转换。先跑 tools/derive_lexique_phon.py\n" % PHON_MAP)


def lex_to_ipa(code):
    """把 Lexique 音素编码串转成 IPA。遇到未知编码写 ? 并记入统计。

    转换后统一过一遍鼻化元音改写（真实发音标法）：
      ɛ̃ / œ̃ -> ã     ɑ̃ -> ɒ̃     ɔ̃ -> õ
    见 tools/nasal_style.py。放在这里做，保证词库、音标词典、例句三处
    用的是同一套音标体系，不会一个地方改了另一个没改。
    """
    if not code:
        return ""
    out = []
    for c in code:
        v = PHON_TO_IPA.get(c)
        if v is None:
            out.append("?")
            UNKNOWN_PHON.add(c)
        else:
            out.append(v)
    return convert_nfc("".join(out))


UNKNOWN_PHON = set()


# 词性优先级：同形词（étudiant = 名词/形容词；livre = 名词/动词）取最常用类别
# Lexique 的 cgram 顺序不保证词频序，HOMOGraph 里名词通常排在同形形容词/动词前
POS_MAP = {
    "NOM": "n.m.", "VER": "v.", "AUX": "v.", "ADJ": "adj.", "ADV": "adv.",
    "PRO": "pron.", "PRO:dem": "pron.", "PRO:ind": "pron.", "PRO:per": "pron.",
    "PRO:pos": "pron.", "PRO:rel": "pron.", "PRE": "prép.", "CON": "conj.",
    "ART:def": "art.", "ART:ind": "art.", "ART:part": "art.", "ONO": "onomat.",
    "INT": "interj.", "Sbst": "n.",
}

POS_PRIORITY = ["NOM", "VER", "AUX", "ADJ", "ADV", "PRE", "CON", "PRO",
                "ART:def", "ART:ind", "ART:part", "INT", "ONO"]


def pick_pos(rec):
    """从 Lexique 记录的多个 cgram 里挑最合适的一个，并补性别。"""
    if not rec or not rec.get("cgram"):
        return ""
    best = None
    best_rank = 999
    for cg in rec["cgram"]:
        base = cg.split(":")[0]
        try:
            r = POS_PRIORITY.index(base)
        except ValueError:
            r = 998
        if r < best_rank:
            best_rank = r
            best = cg
    if not best:
        best = rec["cgram"][0]
    p = POS_MAP.get(best, "")
    if not p:
        p = POS_MAP.get(best.split(":")[0], "")
    if best.split(":")[0] == "NOM":
        g = (rec.get("genre") or "").lower()
        if g == "f":
            p = "n.f."
        elif g == "m":
            p = "n.m."
        else:
            p = "n."
    return p


def load_lexique():
    """ortho -> {phon: [..], cgram: {..}, genre, nombre}"""
    idx = {}
    if not os.path.exists(LEXIQUE):
        sys.stderr.write("缺少 Lexique383.tsv：%s\n" % LEXIQUE)
        return idx
    with io.open(LEXIQUE, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        try:
            i_o = header.index("ortho")
            i_p = header.index("phon")
            i_c = header.index("cgram")
            i_g = header.index("genre")
            i_n = header.index("nombre")
        except ValueError:
            sys.stderr.write("Lexique383 表头不符合预期\n")
            return idx
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_p, i_c, i_g, i_n):
                continue
            w = p[i_o].strip()
            if not w:
                continue
            key = w.lower()
            rec = idx.setdefault(key, {"phon": [], "cgram": [], "genre": "", "nombre": ""})
            ph = p[i_p].strip()
            if ph and ph not in rec["phon"]:
                rec["phon"].append(ph)
            cg = p[i_c].strip()
            if cg and cg not in rec["cgram"]:
                rec["cgram"].append(cg)
            if not rec["genre"]:
                rec["genre"] = p[i_g].strip()
            if not rec["nombre"]:
                rec["nombre"] = p[i_n].strip()
    return idx


# ---------------- 解析 CFDICT ----------------
CFDICT_LINE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+/(.*)/\s*$")


def parse_cfdict(path):
    """simp -> [(pinyin, [gloss, ...]), ...]"""
    out = collections.OrderedDict()
    if not os.path.exists(path):
        sys.stderr.write("缺少 cfdict.u8：%s\n" % path)
        return out
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            m = CFDICT_LINE.match(line.rstrip("\n"))
            if not m:
                continue
            trad, simp, py, gloss = m.groups()
            parts = [g.strip() for g in gloss.split("/") if g.strip()]
            if not parts:
                continue
            out.setdefault(simp, []).append({"py": py, "trad": trad, "gloss": parts})
    return out


# ---------------- 解析 CEDICT（提供英文义项兜底 + 更全的词头） ----------------
CEDICT_LINE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+/(.*)/\s*$")


def parse_cedict(path):
    out = collections.OrderedDict()
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            m = CEDICT_LINE.match(line.rstrip("\n"))
            if not m:
                continue
            trad, simp, py, gloss = m.groups()
            parts = [g.strip() for g in gloss.split("/") if g.strip()]
            if not parts:
                continue
            out.setdefault(simp, []).append({"py": py, "trad": trad, "gloss": parts})
    return out


# ---------------- 清理 ----------------
# CFDICT 里常见的非义项内容
NOISE = re.compile(
    r"^(radical|numéro|n°|voir |cf\.|var\.|variante|abbréviation|symbole|"
    r"dans la numération|première lettre|lettre de l'alphabet)", re.I)
PAREN_NOTE = re.compile(r"[（(][^）)]*[）)]")


def clean_gloss(g):
    g = g.strip().strip(".")
    # 规范化：去 (fig.)/qqn 类缩写括注、修括号不平衡、压缩空白
    g, _ = norm_sense(g)
    # 已确认的拼写错误
    g = fix_known_misspellings(g)
    g = re.sub(r"\s+", " ", g).strip()
    # 去掉纯分类标记
    if g.lower().startswith(("radical ", "n°", "no ")):
        return ""
    if NOISE.match(g):
        return ""
    # 去掉整条只是词典缩写的（qqn / qch / loc. …）
    if not g or is_abbrev(g):
        return ""
    # 去掉纯数字 / 纯符号（"7"、"100"、"1D"、"1984 (roman)"）
    if re.fullmatch(r"[\d\s.,()\-+A-Z]*", g) and not re.search(r"[a-zà-ÿ]{2,}", g):
        return ""
    # 去掉「85e radical」「1 dans la numération Suzhou」这类部首/编码说明
    if re.search(r"\b(\d+e|e|ème|ième)?\s*radical\b", g, re.I):
        return ""
    if re.search(r"numération|bopomofo|dans la numération", g, re.I):
        return ""
    # 去掉拉丁学名（双名法：属名 + 种加词，斜体惯例）
    if re.fullmatch(r"[A-Z][a-z]+ [a-z]{3,}", g):
        return ""
    # 去掉整条都是括号注记的（"(soie)"、"(variété d'herbe)"）
    if re.fullmatch(r"[（(][^）)]*[）)]", g):
        return ""
    if len(g) > 60:
        return ""
    return g


def is_latin_french(s):
    """义项里不该有汉字（有就是数据污染）"""
    return not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", s)


# ---------------- 短语级音标标注 ----------------
# 功能词（闭类）：Lexique383 里大多也能查到，这里补的是「查不到时」的兜底，
# 以及短语里不该被当成实词去匹配的高频虚词。
CLITIC_IPA = {
    "le": "lə", "la": "la", "les": "le", "l'": "l", "un": "œ̃", "une": "yn",
    "des": "de", "du": "dy", "de": "də", "d'": "d", "au": "o", "aux": "o",
    "à": "a", "et": "e", "ou": "u", "où": "u", "en": "ɑ̃", "y": "i",
    "ne": "nə", "n'": "n", "se": "sə", "s'": "s", "ce": "sə", "c'": "s",
    "que": "kə", "qu'": "k", "qui": "ki", "quoi": "kwa", "dont": "dɔ̃",
    "il": "il", "elle": "ɛl", "ils": "il", "elles": "ɛl", "on": "ɔ̃",
    "je": "ʒə", "j'": "ʒ", "tu": "ty", "nous": "nu", "vous": "vu",
    "me": "mə", "m'": "m", "te": "tə", "t'": "t", "lui": "lɥi", "leur": "lœʁ",
    "mon": "mɔ̃", "ma": "ma", "mes": "me", "ton": "tɔ̃", "ta": "ta", "tes": "te",
    "son": "sɔ̃", "sa": "sa", "ses": "se", "notre": "nɔtʁ", "votre": "vɔtʁ",
    "nos": "no", "vos": "vo", "leurs": "lœʁ",
    "pour": "puʁ", "par": "paʁ", "avec": "a.vɛk", "sans": "sɑ̃", "sous": "su",
    "sur": "syʁ", "dans": "dɑ̃", "entre": "ɑ̃tʁ", "vers": "vɛʁ", "chez": "ʃe",
    "mais": "mɛ", "si": "si", "comme": "kɔm", "car": "kaʁ", "donc": "dɔ̃k",
    "or": "ɔʁ", "ni": "ni", "très": "tʁɛ", "plus": "ply", "moins": "mwɛ̃",
    "tout": "tu", "tous": "tus", "toute": "tut", "toutes": "tut",
    "bien": "bjɛ̃", "mal": "mal", "aussi": "o.si", "encore": "ɑ̃.kɔʁ",
    "déjà": "de.ʒa", "toujours": "tu.ʒuʁ", "jamais": "ʒa.mɛ",
    "être": "ɛtʁ", "avoir": "a.vwaʁ", "faire": "fɛʁ", "aller": "a.le",
    "pouvoir": "pu.vwaʁ", "vouloir": "vu.lwaʁ", "devoir": "də.vwaʁ",
    "savoir": "sa.vwaʁ", "voir": "vwaʁ", "venir": "və.niʁ", "prendre": "pʁɑ̃dʁ",
}

# 短语里允许跳过的标记
SKIP_TOKEN = re.compile(r"^[.,;:!?()\[\]«»\"'…]+$")


def annotate_phrase(sense, lex):
    """给一条法语义项标音标。

    返回 (ipa_string, pos_string, hit_words, total_words)

    规则：
      - 逐词查 Lexique383（唯一可信来源），Lexique 编码经 lex_to_ipa 转 IPA；
      - 查不到就查闭类功能词表（这些词的音标是确定无疑的，不属于"猜"）；
      - 仍查不到则写 "?"，不计入命中——UI 标「待核」。

    **不使用规则式 G2P 兜底**：实测 tools/eval_g2p.py 在 3000 条抽样上精确匹配率
    只有 50.4%，用它填充剩余词条等于一半音标是错的，违反红线 R5。
    规则 G2P 仅保留作人工核对时的参考候选，不进成品数据。
    """
    raw = sense.strip()
    raw = PAREN_NOTE.sub(" ", raw)                    # 去掉括注说明
    raw = re.sub(r"^(littéralement|lit\.|fig\.|fam\.|arg\.|vx\.|arch\.|dial\.)\s*:?\s*",
                 "", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw).strip(" .;,")
    if not raw:
        return "", "", 0, 0

    pos_out = ""
    tokens = []          # [(surface, ipa_or_None, is_content)]
    total = 0
    hit = 0
    content_pos = ""

    for tok in raw.split(" "):
        if not tok or SKIP_TOKEN.match(tok):
            continue

        # 词典缩写（qqn / qch / fig …）不是义项内容，跳过不标音标
        if is_abbrev(tok):
            continue

        # 省音缩合：d'un / l'argent / n'aboutir / j'ai / qu'il
        # 撇号左边是虚词（本身有确定音标），右边才是实词
        head, tail = split_elision(tok)
        if head:
            total += 1
            hit += 1
            tok = tail
            if not tok:
                continue

        # 连字符复合词（peut-être / grand-père）：逐段查，用 - 连接
        parts = tok.split("-")
        part_ipa, part_ok = [], True
        for p in parts:
            if not p:
                continue
            lp = p.lower()
            total += 1
            rec = lex.get(lp)
            if rec and rec["phon"]:
                part_ipa.append(lex_to_ipa(rec["phon"][0]))
                hit += 1
                if not content_pos:
                    content_pos = pick_pos(rec)
            elif lp in CLITIC_IPA:
                part_ipa.append(CLITIC_IPA[lp])
                hit += 1
            else:
                # 词形变化（复数 -s、动词变位）回落：去 s / 去 es 再试
                alt = None
                if lp.endswith("s") and lex.get(lp[:-1]):
                    alt = lex[lp[:-1]]["phon"]
                elif lp.endswith("es") and lex.get(lp[:-2]):
                    alt = lex[lp[:-2]]["phon"]
                if alt:
                    part_ipa.append(lex_to_ipa(alt[0]))
                    hit += 1
                else:
                    part_ipa.append("?")
                    part_ok = False

        tok_ipa = "-".join(part_ipa)
        tokens.append((tok, tok_ipa, part_ok))

    if not tokens:
        return "", "", 0, 0

    ipa = " ".join(t[1] for t in tokens)

    # 只保留实词音标作为「主音标」也可以，但整体序列更有用；这里返回整条
    if hit == 0:
        return "", content_pos, 0, total
    return ipa, content_pos, hit, total


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sys.stderr.write("加载繁简表：ST %d / TS %d\n" % (len(ST), len(TS)))
    lex = load_lexique()
    sys.stderr.write("Lexique383 词形 %d 条\n" % len(lex))

    cf = parse_cfdict(CFDICT)
    ce = parse_cedict(CEDICT)
    sys.stderr.write("CFDICT 词头 %d 条 / CEDICT 词头 %d 条\n" % (len(cf), len(ce)))

    # 合并词头集合：以 CFDICT 为主（有法语），CEDICT 补长尾（但无法语时跳过）
    heads = list(cf.keys())
    if args.limit:
        heads = heads[:args.limit]
    sys.stderr.write("待构建 %d 条\n" % len(heads))

    rows = []
    src_dump = []
    report = []
    stat = collections.Counter()

    for simp in heads:
        entries = cf[simp]
        if len(simp) > MAX_WORD_LEN:
            stat["skip_toolong"] += 1
            continue

        # 拼音：取出现次数最多的
        pycnt = collections.Counter(e["py"] for e in entries)
        py = pycnt.most_common(1)[0][0]

        # 繁体：优先用 CFDICT 自带的 trad
        trad = simp
        cand_trads = [e["trad"] for e in entries if e["trad"] and e["trad"] != simp]
        if cand_trads:
            trad = collections.Counter(cand_trads).most_common(1)[0][0]
        elif simp in ST:
            trad = to_trad(simp)
        stat["trad_from_cfdict" if cand_trads else "trad_from_opencc"] += 1

        # 义项：按出现顺序去重，清洗后取前 5
        senses, seen = [], set()
        for e in entries:
            for g in e["gloss"]:
                c = clean_gloss(g)
                if not c:
                    continue
                if not is_latin_french(c):
                    stat["gloss_with_cjk"] += 1
                    continue
                k = c.lower()
                if k in seen:
                    continue
                seen.add(k)
                senses.append(c)
                if len(senses) >= MAX_SENSES:
                    break
            if len(senses) >= MAX_SENSES:
                break

        if not senses:
            stat["no_sense"] += 1
            continue

        # IPA / 词性：逐义项查 Lexique383
        #
        # CFDICT 的义项有 46% 是短语（froid mordant / être des chacals de la même
        # tanière…）。Lexique383 只有单词词形，直接拿整条短语去查必然落空——
        # 第一版就是这样把覆盖率压到 38.5% 的。
        #
        # 正确做法：按**词**挂音标，短语按词序列逐词标注。
        #   "eau"                  -> "o"
        #   "froid mordant"        -> "fʁwa mɔʁ.dɑ̃"
        #   "être des chacals…"    -> 逐个实词查，虚词用闭类表
        ipas, poss = [], []
        hit_words = 0
        total_words = 0
        for s in senses:
            ipa, pos, n_hit, n_tot = annotate_phrase(s, lex)
            ipas.append(ipa)
            poss.append(pos)
            hit_words += n_hit
            total_words += n_tot

        hit = hit_words
        stat["total"] += 1
        if hit_words >= total_words and total_words > 0:
            stat["ipa_full"] += 1
        elif hit_words > 0:
            stat["ipa_partial"] += 1
        else:
            stat["ipa_none"] += 1

        conf = round(hit_words / total_words, 3) if total_words else 0.0
        meta = {"src": "CFDICT", "tier": "L1", "conf": conf}
        if conf < 1.0:
            meta["pending"] = "ipa"

        rows.append([trad, simp, pinyin_display(py), "；".join(senses),
                     "；".join(ipas), "；".join(poss), "", meta])
        src_dump.append({"s": simp, "t": trad, "y": pinyin_display(py),
                         "g": senses, "ipa": ipas, "pos": poss, "hit": hit})
        report.append((simp, len(senses), hit, "" if hit == len(senses) else "ipa_missing"))

    # 排序：先短词后长词，再按字典序（与汉南一致，便于前缀检索）
    rows.sort(key=lambda r: (len(r[1]), r[1]))

    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    with io.open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("window.ZF=" + payload + ";\n")

    with io.open(OUT_SRC, "w", encoding="utf-8") as f:
        f.write(json.dumps(src_dump, ensure_ascii=False, separators=(",", ":")))

    with io.open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("词头\t义项数\tIPA命中\t问题\n")
        for s, n, h, iss in report:
            f.write("%s\t%d\t%d\t%s\n" % (s, n, h, iss))

    total = stat["total"] or 1
    stats = {
        "entries": len(rows),
        "ipa_full": stat["ipa_full"],
        "ipa_partial": stat["ipa_partial"],
        "ipa_none": stat["ipa_none"],
        "ipa_coverage_full": round(stat["ipa_full"] / total, 4),
        "ipa_coverage_any": round((stat["ipa_full"] + stat["ipa_partial"]) / total, 4),
        "no_sense": stat["no_sense"],
        "skip_toolong": stat["skip_toolong"],
        "gloss_with_cjk_dropped": stat["gloss_with_cjk"],
        "size_mb": round(len(payload.encode("utf-8")) / 1048576, 2),
        "built": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
    }
    with io.open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=2))

    print("词条 %d" % stats["entries"])
    print("IPA 全覆盖 %d / 部分 %d / 无 %d" % (stats["ipa_full"], stats["ipa_partial"], stats["ipa_none"]))
    print("IPA 覆盖率（全）%.1f%%  （含部分）%.1f%%"
          % (stats["ipa_coverage_full"] * 100, stats["ipa_coverage_any"] * 100))
    print("体积 %.1f MB -> %s" % (stats["size_mb"], OUT_JS))


if __name__ == "__main__":
    main()