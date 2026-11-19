#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_frdetail.py — 构建法语词条详情（v2：以拉鲁斯双解词典为主源）

为什么重写：
  v1 的中文释义是从 CFDICT 反演的，而 CFDICT 是**单词对译**词典：
      䍃 䍃 [yao2] /vase/pichet/
      佼 佼 [jiao3] /beau/
  于是法语词 beau 的中文成了一批古汉语单字（㑇/丽/佳/佼/倢/倩/奕/妍）。
  这不是过滤能修的，是数据源形式不对。

  v2 改用《拉鲁斯法汉双解词典》（mahavivo/larousse）：
    每个义项 = 法语释义 + 中文对应词 + 例句，还有词性、音标。
  这才是法汉词典该有的东西。

各数据源分工：
  中文释义 / 词性 / 音标  <- 拉鲁斯双解（33,597 词条 / 68,637 义项）
  近义 / 反义 / 联想      <- WOLF 法文词网
  派生                    <- 构词法（french_morph），共享词根才算
  词根                    <- 构词法
  例句                    <- frex.js（另由 build_fr_examples.py 生成）

词形还原：
  abandonné / abjectement 这类变位、派生形式，Larousse 没有独立词条。
  按「还原到原型再挂字典释义」处理，并在词条上注明是哪个原型的什么形式。

    python tools/build_frdetail.py
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from french_morph import root_of, same_family  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
LAROUSSE = os.path.join(ROOT, "data", "larousse_senses.jsonl")
WOLF = os.path.join(RAW, "wolf.xml")
OUT = os.path.join(ROOT, "app", "frdetail.js")
OUT_STATS = os.path.join(ROOT, "data", "frdetail_stats.json")

MAX_SENSES = 12
MAX_PER_REL = 8

REL_ZH = {
    "near_antonym": "ant", "antonym": "ant",
    "eng_derivative": "deriv", "derived": "deriv",
    "similar_to": "similar", "also_see": "also", "verb_group": "vg",
}
KEEP_REL = {"ant", "deriv", "also", "similar", "vg"}


def load_larousse():
    """拉鲁斯：词 -> {pos, ipa, s:[{fr,zh,ex,pos,dom}]}"""
    out = {}
    with io.open(LAROUSSE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[r["h"].lower()] = r
    return out


def parse_wolf():
    if not os.path.exists(WOLF):
        return {}, {}
    s = io.open(WOLF, encoding="utf-8").read()
    blocks = re.findall(r"<SYNSET>(.*?)</SYNSET>", s, re.S)
    sys.stderr.write("WOLF SYNSET %d\n" % len(blocks))

    synsets = {}
    word_syn = collections.defaultdict(set)
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
        rels = collections.defaultdict(set)
        for m in re.finditer(r'<ILR type="([^"]+)">([^<]+)</ILR>', b):
            rt = REL_ZH.get(m.group(1))
            if rt:
                rels[rt].add(m.group(2))
        synsets[sid] = {"pos": pos, "rels": {k: list(v) for k, v in rels.items()}}
        for w in lits:
            word_syn[(w.lower(), pos)].add(sid)
            syn_members[sid].add((w.lower(), pos))

    return synsets, word_syn, syn_members


def build_relations(synsets, word_syn, syn_members):
    out = collections.defaultdict(lambda: collections.defaultdict(set))
    for key, sids in word_syn.items():
        w, pos = key
        for sid in sids:
            for (o, _p) in syn_members.get(sid, ()):
                if o != w:
                    out[key]["syn"].add(o)
            for rtype, targets in synsets[sid]["rels"].items():
                if rtype not in KEEP_REL:
                    continue
                for t in targets:
                    for (o, _p) in syn_members.get(t, ()):
                        if o != w:
                            out[key][rtype].add(o)
    return out


def main():
    sys.stderr.write("加载拉鲁斯双解...\n")
    LAR = load_larousse()
    sys.stderr.write("  %d 个词条\n" % len(LAR))

    sys.stderr.write("解析 WOLF...\n")
    synsets, word_syn, syn_members = parse_wolf()
    sys.stderr.write("构建语义关系...\n")
    rels = build_relations(synsets, word_syn, syn_members)

    # 需要处理的法语词：拉鲁斯全部 + WOLF 里的形态词
    words = set(LAR.keys())
    for (w, _p) in word_syn.keys():
        if re.match(r"^[a-zà-ÿœæç'-]+$", w):
            words.add(w)
    sys.stderr.write("候选词 %d\n" % len(words))

    DETAIL = {}
    stats = collections.Counter()

    for w in sorted(words):
        rec = {}

        # ---- 释义：优先拉鲁斯 ----
        lar = LAR.get(w)
        lemma_of = None
        if not lar:
            # ---- 词形还原：变位/派生形式挂到原型 ----
            # 注意同形冲突：livre 既是名词「书」，也是动词 livrer 的变位。
            # 必须**先查拉鲁斯原生词条**，查不到才做还原——
            # 早期版本反过来，结果查 livre 显示的是 livrer 的「交付」。
            lemma = None
            cands = []
            for suf in ("s", "e", "es", "ée", "ées", "és", "é"):
                if w.endswith(suf) and len(w) > len(suf) + 2:
                    cands.append(w[: -len(suf)])
            for suf in ("er", "ir", "re", "ant", "ment"):
                if w.endswith(suf) and len(w) > len(suf) + 2:
                    cands.append(w[: -len(suf)])
                    if suf == "ment":
                        cands.append(w[:-4] + "e")
                        cands.append(w[:-4] + "er")
            for c in cands:
                if c in LAR:
                    lemma = c
                    break
            if lemma:
                lar = LAR[lemma]
                lemma_of = lemma

        if lar:
            senses = []
            for s in lar["s"][:MAX_SENSES]:
                item = {"fr": s["fr"]}
                if s.get("zh"):
                    item["zh"] = s["zh"]
                if s.get("pos"):
                    item["pos"] = s["pos"]
                if s.get("dom"):
                    item["dom"] = s["dom"]
                if s.get("ex"):
                    item["ex"] = s["ex"]
                if item["fr"] or item.get("zh"):
                    senses.append(item)
            if senses:
                rec["s"] = senses
                stats["with_senses"] += 1
                if any(x.get("zh") for x in senses):
                    stats["with_zh"] += 1
            if lar.get("pos"):
                rec["pos"] = lar["pos"]
                stats["with_pos"] += 1
            if lar.get("ipa"):
                rec["ipa"] = lar["ipa"]
                stats["with_ipa"] += 1
        else:
            # 原生词条与原型都查不到 -> 只有 WOLF 关系，无释义
            stats["no_senses"] += 1

        # ---- 近义/反义/派生/联想 ----
        best, best_score = None, -1
        for p in ("n", "v", "a", "b"):
            key = (w, p)
            if key in rels:
                sc = sum(len(rels[key].get(r, ())) for r in KEEP_REL)
                if sc > best_score:
                    best_score, best = sc, rels[key]
        if best:
            for r in ("syn", "ant"):
                vals = sorted(best.get(r, ()))
                if vals:
                    rec[r] = vals[:MAX_PER_REL]
                    stats["with_" + r] += 1

            raw_deriv = sorted(best.get("deriv", ()))
            true_deriv, assoc = [], []
            for v in raw_deriv:
                (true_deriv if same_family(w, v) else assoc).append(v)
            if true_deriv:
                rec["deriv"] = true_deriv[:MAX_PER_REL]
                stats["with_deriv"] += 1
            if assoc:
                rec["assoc"] = assoc[:MAX_PER_REL]
                stats["with_assoc"] += 1
            also = sorted(best.get("also", ()))
            if also:
                merged = list(rec.get("assoc", []))
                for v in also:
                    if v not in merged:
                        merged.append(v)
                rec["assoc"] = merged[:MAX_PER_REL]

            rt = root_of(w)
            if len(rt) >= 3 and rt != w:
                rec["root"] = rt
                stats["with_root"] += 1

        if rec:
            DETAIL[w] = rec

    # 第二阶段：按词根补派生
    sys.stderr.write("按词根补派生...\n")
    root_groups = collections.defaultdict(list)
    for w in words:
        rt = root_of(w)
        if len(rt) >= 4:
            root_groups[rt].append(w)
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
                if o == w or o in cur or len(o) <= len(w):
                    continue
                cur.append(o)
                if len(cur) >= MAX_PER_REL:
                    break
            if cur:
                rec["deriv"] = sorted(cur)[:MAX_PER_REL]
                root_added += 1
    stats["deriv_from_root"] = root_added

    js = "window.FRDETAIL=" + json.dumps(DETAIL, ensure_ascii=False,
                                         separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")
    with io.open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write(json.dumps(dict(stats), ensure_ascii=False, indent=2))

    print("\n法语词条 %d 条 -> %s（%.2f MB）"
          % (len(DETAIL), OUT, len(js.encode("utf-8")) / 1048576))
    for k in sorted(stats):
        print("  %-22s %d" % (k, stats[k]))

    print("\n抽样：")
    for w in ("maison", "beau", "livre", "manger", "grand", "eau"):
        r = DETAIL.get(w)
        if not r:
            continue
        print("  【%s】pos=%s 义项 %d" % (w, "/".join(r.get("pos", [])), len(r.get("s", []))))
        for s in r.get("s", [])[:2]:
            print("     %s | 中：%s" % (s.get("fr", "")[:44], s.get("zh", "")))


if __name__ == "__main__":
    main()
