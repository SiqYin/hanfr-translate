#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_h_aspire.py — 从 fr.wiktionary 分类拉取 h aspiré 词表，并用 Lexique383 交叉校验

为什么两段式：
  fr.wiktionary 的 "Termes en français à h aspiré" 分类里混有大量**外语**词条
  （alif / Aue / 8.6 / 11e …），直接用会污染联诵判定。
  但 Lexique383 只有法语词形。两者取交集，剩下的就是真·法语 h aspiré 词，
  既权威又可复核，不需要我凭记忆手写。

输出：
  data/raw/fr_h_aspire_wikt.txt      维基分类原始名单
  data/fr_h_aspire.tsv               交集后的最终表（词<TAB>类别）
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT_TSV = os.path.join(ROOT, "data", "fr_h_aspire.tsv")
LEXIQUE = os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据", "Lexique383.tsv")

CAT = "Catégorie:Termes en français à h aspiré"
API = "https://fr.wiktionary.org/w/api.php"
UA = ("HanFrDictBuilder/0.1 (https://github.com/SiqYin; contact: local build) "
      "python-urllib")


def api(params, tries=4):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                raise
            wait = 3.0 * (i + 1)
            sys.stderr.write("  重试 %d/%d（%s），等 %.0fs\n" % (i + 1, tries, e, wait))
            time.sleep(wait)


def fetch_category():
    """分页拉全部分类成员。每页之间停 1.5 秒，遵守 MediaWiki 速率建议。"""
    names = []
    cont = None
    page = 0
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": CAT,
             "cmlimit": 500, "cmnamespace": 0, "format": "json"}
        if cont:
            p["cmcontinue"] = cont
        try:
            j = api(p)
        except Exception as e:
            sys.stderr.write("分页在第 %d 页失败：%s，保留已取的 %d 条\n" % (page, e, len(names)))
            break
        mem = (j.get("query") or {}).get("categorymembers") or []
        names.extend(m.get("title", "") for m in mem)
        page += 1
        sys.stderr.write("  第 %d 页：累计 %d\n" % (page, len(names)))
        cont = (j.get("continue") or {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(1.5)
    return [n for n in names if n]


def load_lexique_ortho():
    """Lexique383 的全部法语词形（小写）。这是「合法法语词」的判据。"""
    path = os.path.normpath(LEXIQUE)
    if not os.path.exists(path):
        sys.stderr.write("找不到 Lexique383.tsv：%s\n" % path)
        return set()
    s = set()
    with io.open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        try:
            i_ortho = header.index("ortho")
        except ValueError:
            i_ortho = 0
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) > i_ortho:
                w = p[i_ortho].strip().lower()
                if w:
                    s.add(w)
    return s


def main():
    os.makedirs(RAW, exist_ok=True)
    raw_path = os.path.join(RAW, "fr_h_aspire_wikt.txt")

    if os.path.exists(raw_path) and os.path.getsize(raw_path) > 1000:
        sys.stderr.write("复用已下载的维基名单 %s\n" % raw_path)
        names = [l.strip() for l in io.open(raw_path, encoding="utf-8") if l.strip()]
    else:
        sys.stderr.write("拉取 %s …\n" % CAT)
        names = fetch_category()
        with io.open(raw_path, "w", encoding="utf-8") as f:
            f.write("\n".join(names))
        sys.stderr.write("维基名单 %d 条 -> %s\n" % (len(names), raw_path))

    lex = load_lexique_ortho()
    sys.stderr.write("Lexique383 词形 %d 条\n" % len(lex))

    # 交集：维基分类 ∩ Lexique 法语词形
    keep = []
    dropped = []
    for n in names:
        w = n.strip()
        if not w or " " in w:          # 多词短语不入表（联诵判定按单词做）
            dropped.append(w)
            continue
        lw = w.lower()
        if lw in lex:
            keep.append(w)
        else:
            dropped.append(w)

    keep = sorted(set(keep), key=lambda x: (x.lower(), x))
    with io.open(OUT_TSV, "w", encoding="utf-8") as f:
        f.write("# h aspiré 词表（fr.wiktionary 分类 ∩ Lexique383 法语词形）\n")
        f.write("# 生成脚本：tools/fetch_h_aspire.py　不要手改，重跑脚本即可\n")
        f.write("# 格式：词\\t类别\n")
        for w in keep:
            f.write("%s\th-aspire\n" % w)

    sys.stderr.write("\n维基原始 %d 条 -> 法语交集 %d 条（剔除非法语/短语 %d 条）\n"
                     % (len(names), len(keep), len(dropped)))
    sys.stderr.write("写出 %s\n" % OUT_TSV)

    # 抽样自检：这几个必须是 h aspiré
    probe = ["héros", "hibou", "honte", "haut", "hache", "hérisson"]
    ks = {w.lower() for w in keep}
    for p in probe:
        sys.stderr.write("  自检 %-10s %s\n" % (p, "在表内 ✓" if p in ks else "缺失 ✗"))
    # 这几个必须是 h muet（不应在表内）
    probe2 = ["huile", "humble", "humour", "hier", "homme", "heure", "hiver", "hôpital"]
    for p in probe2:
        sys.stderr.write("  反自检 %-10s %s\n" % (p, "不在表内 ✓" if p not in ks else "误入 ✗"))


if __name__ == "__main__":
    main()