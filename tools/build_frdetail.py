#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_frwiktionary.py — 构建法语词条详情数据（释义/词性/阴阳性/短语/近义反义/派生词根）

用户需求（v1.0.2 剩余部分）：
  输入法语词，给出
    1. 中文释义（逐条列出）
    2. 词性标记（n.f. / n.m. / v.t. 这类通用写法）
    3. 阴阳性
    4. 常见短语、常用词组
    5. 近义词、反义词、联想词
    6. 派生、词根
    7. 例句（已有）
    8. 全部变位（已有）

数据来源（各有分工，不能用同一个源硬凑）：
  词性/阴阳性  <- Lexique 的 cgram + genre 字段（权威、机器可读）
  近义/反义/派生/词根 <- WOLF 法文词网（117,658 个同义词集）
  常见短语    <- CFDICT 反演（已有的 fr2zh 数据）
  中文释义    <- CFDICT 义项 + Index-Translate（**不自己编**）

中文释义这条最需要谨慎：
  不能拿模型直接生成。做法是：
    1. 法语词在 CFDICT 里出现过的义项 -> 取对应中文词头（这是词典数据，可靠）
    2. 没有的 -> 标「待补」，不编造
  宁可缺，不可编——与音标同一条原则。

输出：
  app/frdetail.js   window.FRDETAIL = {"maison": {...}}

    python tools/build_frdetail.py
"""
import collections
import csv
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from french_morph import root_of, same_family  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
WOLF = os.path.join(RAW, "wolf.xml")
SRC_ZHFR = os.path.join(ROOT, "app", "zhfr.js")
OUT = os.path.join(ROOT, "app", "frdetail.js")
OUT_STATS = os.path.join(ROOT, "data", "frdetail_stats.json")
OUT_REPORT = os.path.join(ROOT, "data", "frdetail_report.tsv")

# WOLF POS -> 通用法语词性标记
POS_MAP = {
    "n": "n.", "v": "v.", "a": "adj.", "b": "adv.",
    "r": "adv.", "s": "adj.",
}

# WOLF 关系类型 -> 中文名
REL_ZH = {
    "near_antonym": "ant",
    "antonym": "ant",
    "eng_derivative": "deriv",
    "derived": "deriv",
    "hypernym": "hyper",
    "similar_to": "similar",
    "also_see": "also",
    "verb_group": "verbgroup",
}

# 只保留这几类，避免数据爆炸
KEEP_REL = {"ant", "deriv", "also", "similar"}

MAX_PER_REL = 8


def parse_wolf():
    """解析 WOLF：返回
       word_pos -> [(synset_id, [synonyms], def, pos)]
       synset_id -> info
       word -> {"syn": set, "ant": set, "deriv": set, "also": set}
    """
    if not os.path.exists(WOLF):
        sys.stderr.write("缺 WOLF：%s\n" % WOLF)
        return {}, {}, collections.defaultdict(lambda: collections.defaultdict(set))

    s = io.open(WOLF, encoding="utf-8").read()
    blocks = re.findall(r"<SYNSET>(.*?)</SYNSET>", s, re.S)
    sys.stderr.write("WOLF SYNSET %d\n" % len(blocks))

    synsets = {}
    # (word, pos) -> synset ids
    word_syn = collections.defaultdict(set)
    # synset id -> set of (word, pos)
    syn_members = collections.defaultdict(set)

    for b in blocks:
        sid = re.search(r"<ID>([^<]+)</ID>", b)
        pos = re.search(r"<POS>([a-z])</POS>", b)
        if not sid or not pos:
            continue
        sid, pos = sid.group(1), pos.group(1)
        lits = [x for x in re.findall(r"<LITERAL[^>]*>([^<]+)</LITERAL>", b)
                if x != "_EMPTY_"]
        if not lits:
            continue
        d = re.search(r"<DEF>([^<]*)</DEF>", b)
        rels = collections.defaultdict(set)
        for m in re.finditer(r'<ILR type="([^"]+)">([^<]+)</ILR>', b):
            rtype = REL_ZH.get(m.group(1))
            if rtype:
                rels[rtype].add(m.group(2))

        synsets[sid] = {"pos": pos, "lits": lits,
                        "def": (d.group(1).strip() if d else ""),
                        "rels": {k: list(v) for k, v in rels.items()}}
        for w in lits:
            word_syn[(w.lower(), pos)].add(sid)
            syn_members[sid].add((w.lower(), pos))

    return synsets, word_syn, syn_members


def build_relations(synsets, word_syn, syn_members):
    """为每个 (word, pos) 汇总近义/反义/派生/联想。"""
    out = collections.defaultdict(lambda: collections.defaultdict(set))

    for key, sids in word_syn.items():
        w, pos = key
        # 近义：同一 synset 的其他成员
        for sid in sids:
            for (o, _p) in syn_members.get(sid, ()):
                if o != w:
                    out[key]["syn"].add(o)
            # 关系：从该 synset 指向别的 synset
            for rtype, targets in synsets[sid]["rels"].items():
                if rtype not in KEEP_REL:
                    continue
                for t in targets:
                    for (o, _p) in syn_members.get(t, ()):
                        if o != w:
                            out[key][rtype].add(o)
    return out


def load_pos_gender():
    """Lexique：词 -> {pos: set, genre: set}"""
    rec = collections.defaultdict(lambda: {"pos": set(), "genre": set(), "freq": 0})
    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        try:
            i_o = hdr.index("ortho")
            i_c = hdr.index("cgram")
            i_g = hdr.index("genre")
            i_f = hdr.index("freqlemlivres")
        except ValueError:
            return rec
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_c, i_g, i_f):
                continue
            w = p[i_o].strip().lower()
            if not w:
                continue
            r = rec[w]
            if p[i_c]:
                r["pos"].add(p[i_c].strip())
            if p[i_g]:
                r["genre"].add(p[i_g].strip())
            try:
                r["freq"] = max(r["freq"], float(p[i_f] or 0))
            except ValueError:
                pass
    return rec


# 法语名词性别：**不做词尾推断**。
#
# 试过按词尾猜，但法语性别例外太多，猜错的代价比留空更大：
#   maison（-on 多为阳性，但 maison 是阴性）
#   livre（名词阳性，但 livre 也可指「磅」为阴性）
#   page（阴性）、note（阴性）都没有稳定词尾特征
# 实测用词尾规则只能覆盖一半不到，还会把 maison 判成阳性。
#
# 所以：只采用 Lexique 的实测 genre（覆盖 94.6%），
# 缺失的留空，前端显示「待核」。这与音标同一条原则：不确定就不写。
FEM_SUFFIX = ()
MASC_SUFFIX = ()
FEM_EXCEPTIONS = set()
MASC_EXCEPTIONS = set()


def guess_gender(w):
    """已停用。保留函数签名，恒返回空串（不推断）。"""
    return ""


def pos_label(cgram_set, genre_set):
    """Lexique cgram -> 通用法语词性标记（n.f. / n.m. / v.t. 这种）。"""
    labels = []
    for cg in sorted(cgram_set):
        base = cg.split(":")[0]
        if base == "NOM":
            if "f" in genre_set:
                labels.append("n.f.")
            elif "m" in genre_set:
                labels.append("n.m.")
            else:
                labels.append("n.")
        elif base == "VER":
            labels.append("v.")
        elif base == "AUX":
            labels.append("v.aux.")
        elif base == "ADJ":
            labels.append("adj.")
        elif base == "ADV":
            labels.append("adv.")
        elif base == "PRE":
            labels.append("prép.")
        elif base == "CON":
            labels.append("conj.")
        elif base.startswith("PRO"):
            labels.append("pron.")
        elif base.startswith("ART"):
            labels.append("art.")
        elif base == "ONO":
            labels.append("onomat.")
        elif base == "INT":
            labels.append("interj.")
    # 去重保序
    seen, out = set(), []
    for x in labels:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def load_zf():
    src = io.open(SRC_ZHFR, encoding="utf-8").read()
    m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
    return json.loads(m.group(1))


def load_zh_rank():
    """现代汉语常用词表：词 -> 频序号。用于过滤文言/生僻的中文释义。

    为什么必须过滤：
      CFDICT 的义项里有大量文言对应——
        beau  -> 㑇 / 丽 / 佳 / 佼 / 倢 / 倩 / 奕 / 妍
        grand -> 丕 / 丰 / 乔 / 伟 / 俣 / 劭 / 垚 / 壬
      直接展示等于把生僻字词典端给用户。用常用词表筛一遍，
      只留现代汉语真在用的词。
    """
    path = os.path.join(ROOT, "data", "modern_chinese_words.tsv")
    if not os.path.exists(path):
        alt = os.path.normpath(os.path.join(
            ROOT, "..", "..", "..", "2026-11-7 汉南辞典", "01_源码", "hanviet-app",
            "data", "modern_chinese_words.tsv"))
        path = alt if os.path.exists(alt) else path
    rank = {}
    if not os.path.exists(path):
        sys.stderr.write("警告：缺中文常用词表，释义不过滤\n")
        return rank
    with io.open(path, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        try:
            i_w, i_r = hdr.index("词语"), hdr.index("频序号")
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
                continue
            if w not in rank or r < rank[w]:
                rank[w] = r
    return rank


ZH_RANK = {}


def zh_ok(s):
    """中文释义是否可用：必须在现代汉语常用词表内。"""
    if not s or not ZH_RANK:
        return True
    return s in ZH_RANK


# 短语过滤：保留真正的短语 + 带语域/领域标注的用法。
#
# 词典义项里混着几类内容，处理方式不同：
#   (dial.) hauteur d'une maison          <- 方言用法：**保留**（用户明确要求）
#   (famil.) / (argot) / (lit.)  ...      <- 语域标记：保留
#   (botanique) / (musique) ...           <- 领域标记：保留
#   La voix de l'invité domine celle...   <- 完整句子：丢
#   (expr. idiom.) maison très fréquentée <- 「习语」标签但其实是长释义：看词数
#
# 核心判据改成「词数」和「是否成句」，而不是「有没有括注」。
PHRASE_LABEL = re.compile(r"[（(]([^）)]{0,20})[）)]")
PHRASE_MAXWORDS = 6

# 这类标签说明后面是「整句解释」而不是短语，仍要去掉
SENTENCE_LABELS = {"expr. idiom.", "expr.", "loc.", "lit.", "litt.",
                   "c'est-à-dire", "syn.", "ant."}


def strip_label(phrase):
    """去掉括注标签，返回 (纯短语, 标签列表)"""
    labels = [m.group(1).strip().lower() for m in PHRASE_LABEL.finditer(phrase)]
    plain = PHRASE_LABEL.sub(" ", phrase).strip()
    plain = re.sub(r"\s+", " ", plain)
    return plain, labels


# 有意义的标签（语域 + 领域）：前端会显示成小标记
USEFUL_LABELS = {
    # 语域
    "dial.", "dial", "famil.", "famil", "argot", "lit.", "litt.", "vx.",
    "vieilli", "arch.", "arch", "poli", "fig.", "fig", "péj.", "péjor.",
    "vulg.", "poét.", "région.", "canad.", "belg.", "suisse", "afr.",
    # 领域
    "informatique", "musique", "physique", "chimie", "biologie", "anatomie",
    "botanique", "math.", "médecine", "dr.", "droit", "écon.", "pol.",
    "mil.", "marine", "cuis.", "sport", "relig.", "ling.", "zool.",
    "géogr.", "hist.", "techn.", "naut.", "agr.", "imprim.",
}


def is_useful_label(lb):
    if not lb:
        return False
    lb = lb.strip().lower()
    if lb in USEFUL_LABELS:
        return True
    return False


def phrase_ok(phrase, head):
    """判断一条义项能否作为「常见短语」展示。"""
    if not phrase or not head:
        return False

    plain, labels = strip_label(phrase)

    # 「expr. idiom.」这类说明后面通常是整句解释，丢弃
    if any(lb in SENTENCE_LABELS for lb in labels):
        return False

    # 成句的（带句号/问号/感叹号/分号）丢弃
    if re.search(r"[.!?；;]", plain):
        return False

    words = plain.split()
    # 太长的不是短语
    if len(words) > PHRASE_MAXWORDS:
        return False
    # 单个词的也不是短语（那就是词本身）
    if len(words) < 2:
        return False

    # 必须以该词开头，否则是别的词的短语
    if not words[0].lower().startswith(head[:3]):
        return False
    return True


def build_zh_gloss(ZF):
    gloss = collections.defaultdict(list)     # fr -> [zh]
    phrases = collections.defaultdict(set)    # fr -> {含它的中文词头}

    for e in ZF:
        zh = e[1]
        senses = e[3] or ""
        for s in senses.split("；"):
            s = s.strip()
            if not s:
                continue
            # 去掉冠词与括注
            k = re.sub(r"^(le |la |les |l'|un |une |des |du |d'|de )", "", s.lower())
            k = re.sub(r"[（(][^）)]*[）)]", " ", k).strip()
            k = re.sub(r"[.,;:!?«»\"'…\[\]]+$", "", k).strip()
            if not k:
                continue
            if zh not in gloss[k]:
                gloss[k].append(zh)
            # 短语：只收「以该词开头的短词组」，保留语域/领域标注
            for tok in re.split(r"[\s,;:]+", k):
                if 2 < len(tok) and tok != k and phrase_ok(s, tok):
                    plain, labels = strip_label(s)
                    # 只保留有意义的标签（语域 + 领域），丢掉 se/de/nom 这类噪音
                    keep = [lb for lb in labels if is_useful_label(lb)]
                    phrases[tok].add((plain, tuple(keep)))

    return gloss, phrases


def main():
    global ZH_RANK
    ZH_RANK = load_zh_rank()
    sys.stderr.write("中文常用词表 %d 条\n" % len(ZH_RANK))

    sys.stderr.write("加载 Lexique 词性...\n")
    lex = load_pos_gender()
    sys.stderr.write("  %d 个词形\n" % len(lex))

    sys.stderr.write("解析 WOLF...\n")
    synsets, word_syn, syn_members = parse_wolf()
    sys.stderr.write("  同义集 %d，词条 %d\n" % (len(synsets), len(word_syn)))

    sys.stderr.write("构建语义关系...\n")
    rels = build_relations(synsets, word_syn, syn_members)

    sys.stderr.write("读取词库与中文释义...\n")
    ZF = load_zf()
    gloss, phrases = build_zh_gloss(ZF)
    sys.stderr.write("  有中文释义的法语词 %d\n" % len(gloss))

    # 合并：以「词库出现过的法语词」为主，加 WOLF 的常用词
    words = set()
    for e in ZF:
        for s in (e[3] or "").split("；"):
            k = re.sub(r"^(le |la |les |l'|un |une |des |du |d'|de )", "", s.strip().lower())
            k = re.sub(r"[（(][^）)]*[）)]", " ", k).strip()
            k = re.sub(r"[.,;:!?«»\"'…\[\]]+$", "", k).strip()
            if k and " " not in k and re.match(r"^[a-zà-ÿœæç'-]+$", k):
                words.add(k)
    for (w, p) in word_syn.keys():
        if re.match(r"^[a-zà-ÿœæç'-]+$", w):
            words.add(w)

    sys.stderr.write("候选词 %d\n" % len(words))

    DETAIL = {}
    stats = collections.Counter()
    report = []

    for w in sorted(words):
        rec = {}
        # 词性 / 阴阳性
        lx = lex.get(w)
        if lx and lx["pos"]:
            genre = set(lx["genre"])
            is_noun = any(p.startswith("NOM") for p in lx["pos"])
            # 名词但 Lexique 没给性别 -> 标记待核，不推断
            if is_noun and not (genre & {"m", "f"}):
                rec["gpending"] = 1
                stats["gender_pending"] += 1

            labels = pos_label(lx["pos"], genre)
            if labels:
                rec["pos"] = labels
                stats["with_pos"] += 1
            g = sorted(genre)
            if g:
                rec["g"] = g

        # 中文释义：只保留现代汉语常用词，过滤文言与生僻字
        raw_zh = gloss.get(w) or []
        zh = [x for x in raw_zh if zh_ok(x)]
        # 全部被过滤掉说明该词只有文言对应，宁可不显示
        if zh:
            # 按常用度排序（频序号小的在前）
            zh.sort(key=lambda x: (ZH_RANK.get(x, 99999), len(x)))
            rec["zh"] = zh[:8]
            stats["with_zh"] += 1
        elif raw_zh:
            stats["zh_all_rare"] += 1

        # 语义关系（按 pos 汇总，取最全的那组）
        best = None
        best_score = -1
        for p in ("n", "v", "a", "b"):
            key = (w, p)
            if key in rels:
                sc = sum(len(rels[key].get(r, ())) for r in KEEP_REL)
                if sc > best_score:
                    best_score = sc
                    best = rels[key]
        if best:
            # 近义 / 反义：直接采用
            for r in ("syn", "ant"):
                vals = sorted(best.get(r, ()))
                if vals:
                    rec[r] = vals[:MAX_PER_REL]
                    stats["with_" + r] += 1

            # 派生：必须共享词根才算。
            # WOLF 的 eng_derivative 语义太松，直接列会闹笑话：
            #   eau    -> pisser / uriner      （「用水做某事」，不是派生）
            #   grand  -> corbeau              （毫无关系）
            # 只有共享词根的（nation - national、grand - grandeur）才是真派生。
            raw_deriv = sorted(best.get("deriv", ()))
            true_deriv, assoc = [], []
            for v in raw_deriv:
                if same_family(w, v):
                    true_deriv.append(v)
                else:
                    assoc.append(v)
            if true_deriv:
                rec["deriv"] = true_deriv[:MAX_PER_REL]
                stats["with_deriv"] += 1
            # 不共享词根的降级为「联想」，仍保留但对用户诚实
            if assoc:
                rec["assoc"] = assoc[:MAX_PER_REL]
                stats["with_assoc"] += 1

            # also_see 归入联想
            also = sorted(best.get("also", ()))
            if also:
                merged = list(rec.get("assoc", []))
                for v in also:
                    if v not in merged:
                        merged.append(v)
                rec["assoc"] = merged[:MAX_PER_REL]
                stats["with_also"] += 1

            # 词根：只在真正发生了词形变化时才记录。
            # root_of(maison) == maison（没有可剥的前后缀），此时不写，
            # 否则前端会显示「词根 maison」这种无意义信息。
            rt = root_of(w)
            if len(rt) >= 3 and rt != w:
                rec["root"] = rt
                stats["with_root"] += 1

        # 常见短语
        ph = phrases.get(w)
        if ph:
            # ph 里是 (纯短语, 标签元组)，转成 [短语, 标签串] 的结构
            items = []
            for plain, labs in sorted(ph, key=lambda x: (len(x[0]), x[0])):
                if labs:
                    items.append([plain, " / ".join(labs)])
                else:
                    items.append([plain, ""])
            rec["ph"] = items[:8]
            stats["with_ph"] += 1

        if rec:
            DETAIL[w] = rec

    # ---- 第二阶段：用构词法补足派生词 ----
    # WOLF 的派生关系不全（不规则派生如 chanson<-chanter 是缺失的），
    # 这里用词根分组从整个词表里反向找同族词。
    sys.stderr.write("按词根分组补派生...\n")
    root_groups = collections.defaultdict(list)
    for w in words:
        rt = root_of(w)
        if len(rt) >= 4:
            root_groups[rt].append(w)

    # 只处理成员数合理的组，避免超大同根组（如 -tion 一堆）爆炸
    root_added = 0
    for rt, members in root_groups.items():
        if len(members) < 2 or len(members) > 40:
            continue
        for w in members:
            rec = DETAIL.get(w)
            if rec is None:
                continue
            cur = list(rec.get("deriv", []))
            if len(cur) >= MAX_PER_REL:
                continue
            for o in members:
                if o == w or o in cur:
                    continue
                if len(o) <= len(w):
                    # 优先收「更长」的派生词（nation -> national）
                    continue
                cur.append(o)
                if len(cur) >= MAX_PER_REL:
                    break
            if cur:
                rec["deriv"] = sorted(cur)[:MAX_PER_REL]
                root_added += 1
    stats["deriv_from_root"] = root_added
    sys.stderr.write("  按词根补入 %d 个词条的派生\n" % root_added)

    js = "window.FRDETAIL=" + json.dumps(DETAIL, ensure_ascii=False,
                                         separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    with io.open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write(json.dumps(dict(stats), ensure_ascii=False, indent=2))

    print("法语词条详情 %d 条 -> %s（%.2f MB）"
          % (len(DETAIL), OUT, len(js.encode("utf-8")) / 1048576))
    for k in ("with_pos", "with_zh", "with_syn", "with_ant", "with_deriv",
              "with_also", "with_ph"):
        print("  %-12s %d" % (k, stats[k]))

    print("\n抽样：")
    for w in ("maison", "manger", "beau", "grand", "parler", "eau"):
        if w in DETAIL:
            print("  %-8s %s" % (w, json.dumps(DETAIL[w], ensure_ascii=False)[:160]))


if __name__ == "__main__":
    main()
