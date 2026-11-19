#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parse_larousse.py — 解析《拉鲁斯法汉双解词典》

为什么要换数据源：
  原来中→法方向用的是 CFDICT，它是**单词对译**词典（60,438 条），
  没有义项区分、没有词性、没有释义，而且收进了大量文言单字：
      麗 丽 [li4] /beau/
      佼 佼 [jiao3] /beau/
  于是法语词 beau 的中文释义成了「㑇/丽/佳/佼/倢/倩/奕/妍」——
  全是古汉语单字，现代汉语不单独使用。这不是过滤能解决的，
  是数据源本身的形式不对。

  拉鲁斯是**双解词典**：每个义项 = 法语释义 + 中文对应词 + 例句，
  还有词性、音标。这才是法汉词典该有的样子：
      maison [mezɔ̃] n. f. ❶ Bâtiment ... aux personnes 公寓楼: ...
                            ❷ ... 住宅;小洋楼: ...

输入：02_数据管线/原始数据/larousse_fr_zh.json（34,777 条）
输出：data/larousse_senses.jsonl

    python tools/parse_larousse.py
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
SRC = os.path.normpath(os.path.join(
    ROOT, "..", "..", "02_数据管线", "原始数据", "larousse_fr_zh.json"))
OUT = os.path.join(ROOT, "data", "larousse_senses.jsonl")

# 圈号：❶-❿ ⓫-⓿ ❶ 与 ①-⑳
CIRCLED = re.compile(r"[❶❷❸❹❺❻❼❽❾❿⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")
# 词性组分隔
POS_SEP = re.compile(r"[◆◇]")
NUM_PREFIX = re.compile(r"^\d+\.\s*")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# 音标 [..]
IPA_RE = re.compile(r"\[([^\]]+)\]")
# 词性标记
POS_RE = re.compile(
    r"\b(n\.\s?[mf]\.(?:\s?inv\.)?|n\.|adj\.(?:\s?inv\.)?|adv\.|v\.\s?t\.|"
    r"v\.\s?i\.|v\.\s?pron\.|v\.\s?pr\.|prép\.|conj\.|interj\.|art\.|"
    r"pron\.|loc\.\s?adj\.|loc\.\s?adv\.|loc\.\s?n\.|loc\.\s?v\.)")
# 领域/语域标记 〔..〕 〈..〉
DOMAIN_RE = re.compile(r"〔([^〕]{0,12})〕|〈([^〉]{0,12})〉")
# 中文分隔符
ZH_SPLIT = re.compile(r"[,;，；、/｜|]")


def split_pos_groups(text):
    """按 ◆ 分出不同词性的组。"""
    return [g for g in POS_SEP.split(text) if g.strip()]


def parse_group(group):
    """解析一个词性组：返回 (pos, ipa, [sense...])"""
    ipa = ""
    m = IPA_RE.search(group)
    if m:
        ipa = m.group(1).strip()

    pos = ""
    mp = POS_RE.search(group)
    if mp:
        pos = re.sub(r"\s+", " ", mp.group(1)).strip()

    senses = []
    # 用圈号切义项；第一段是词头+音标+词性，跳过。
    #
    # 关键：61% 的条目（21,134 条）**只有一个义项、没有圈号**：
    #     abaisse [abɛs] n. f. (de abaisser). Morceau de pâte ...
    # 早期版本只认圈号，把这六成条目全丢了（34,777 只解析出 13,643）。
    # 没有圈号时，去掉词头/音标/词性后的整段就是一个义项。
    if CIRCLED.search(group):
        parts = CIRCLED.split(group)
        body_parts = parts[1:]
    else:
        # 去掉开头的词头、音标、词性、词源括注，剩下的是释文
        g = group.strip()
        # 去掉开头的 "1. " 编号
        g = NUM_PREFIX.sub("", g)
        # 去掉词头（到音标或词性为止）
        mi = IPA_RE.search(g)
        mp2 = POS_RE.search(g)
        cut = None
        if mi:
            cut = mi.end()
        if mp2 and (cut is None or mp2.start() > cut):
            pass
        if mp2:
            cut = mp2.end() if cut is None else max(cut, mp2.end())
        if cut:
            g = g[cut:]
        # 去掉词源括注 (lat. ...). 或 (de ...).
        g = re.sub(r"^\s*\([^)]{0,80}\)\.?\s*", "", g)
        g = g.strip(" .;:")
        body_parts = [g] if g else []

    for p in body_parts:
        p = p.strip()
        if not p:
            continue
        s = parse_sense(p)
        if s:
            senses.append(s)
    return pos, ipa, senses


def clean_zh_field(s):
    """清洗义项里的中文字段。

    这里能拿到完整上下文，所以比事后按逗号拆分可靠得多。

    实测的脏数据形态（拉鲁斯 OCR 把 〈书〉 这类标记切碎了）：
      mie:  '书,旧〉女友;心爱的女人'
      ire:  '书,旧〉愤怒'
      真释义：'书,书本,书籍'、'吃,食'

    区别在哪：
      '书,旧〉女友' 的「书」后面紧跟的片段以「旧〉」开头 —— 标记残片
      '书,书本,书籍' 后面跟的是「书本」「书籍」—— 正常释义

    规则：如果一个片段后面紧邻的片段含「〉」「〕」等标记尾巴，
    则该片段是标记的一部分，一并丢弃。
    """
    if not s:
        return ""
    # 1. 剥完整标记
    s = re.sub(r"[〈〔\[][^〉〕\]]{0,10}[〉〕\]]", " ", s)
    parts = re.split(r"([,;，；、/])", s)
    out = []
    for i, p in enumerate(parts):
        if re.fullmatch(r"[,;，；、/]", p or ""):
            out.append(p)
            continue
        # 含标记尾巴的片段 -> 丢
        if re.search(r"[〉〕\]]", p):
            out.append(" ")
            continue
        out.append(p)
    s = "".join(out)

    # 2. 处理「书,旧〉女友」被切成 ['书', ',', '旧〉女友'] 的情况：
    #    上一步已把「旧〉女友」整段丢掉，只剩「书,」。
    #    但「书」本身也可能是残片。判据：剩下的片段后面没有内容，
    #    且整条里原本有标记 -> 该片段可疑。
    #    简化处理：若某片段是单个标记字，且同条里有标记被丢弃过，则丢它。
    had_label = bool(re.search(r"[〉〕\]]", s)) or bool(
        re.search(r"[〈〔\[][^〉〕\]]{0,10}[〉〕\]]", s))
    return s.strip()


def strip_etymology(s, max_span=260):
    """去掉开头的词源括注，支持嵌套括号与内部引号。

    只处理**出现在开头或紧跟词性后**的括注，不动正文里的普通括号
    （例如 (par opp. à appartement) 这种是释义的一部分，要保留）。
    """
    if not s:
        return s
    t = s.lstrip()
    # 只匹配开头的括注
    if not t.startswith("("):
        return s
    depth = 0
    i = 0
    n = min(len(t), max_span)
    closed_at = -1
    while i < n:
        ch = t[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                closed_at = i
                break
        i += 1
    if closed_at < 0:
        return s
    head = t[:closed_at + 1]
    # 判断是不是词源：含 lat./gr./de /abrév./probabl./anc./var. 等特征
    if re.search(r"\b(lat|gr|de |abrév|probabl|anc|var\.|du |d'|ital|angl|"
                 r"esp|all|arabe|prov|germ|onomat)", head, re.I):
        rest = t[closed_at + 1:].lstrip(" .;:")
        # 词源后面常跟变位类型标记 [conj. 27]，一并去掉
        rest = re.sub(r"^\s*\[[^\]]{0,24}\]\s*[.,;:]?\s*", "", rest)
        return rest
    return s


def parse_sense(block):
    """从一个义项块里切出 (法语释义, 中文对应词, 例句片段)

    关键：〈书,旧〉 这类语域标记要**整体**归到中文侧。
    它们是「后面的中文词属于书面/古旧用法」的标注，不是法语内容。

    踩过的坑：
      原文 Colère.〈书,旧〉愤怒,恼怒
      按「第一个汉字」切，〈 落在法语侧，于是
        法语 = "Colère.〈书,旧〉"
        中文 = "愤怒,恼怒"
      标记被切开后，下游按逗号拆就得到「书」这个假释义，
      于是「书 -> ire(愤怒)」。
    """
    # 先把词源括注整段去掉。
    #
    # 拉鲁斯的词源括注可能很长并且含引号与嵌套括号：
    #   (probabl. de l'anc. fr. eschiqueté “orné de carreaux…”, de eschequier “échiquier”)
    #   (abrév. de dynamoélectrique “qui transforme l'énergie mécanique
    #    [dynamo-] en énergie électrique”)
    # 朴素的正则 \([^)]*\) 会在内层 ] 或 ) 处断掉，把后面的正文一并吞掉，
    # 于是整条义项的 fr 与 zh 都丢失（实测 5 个词卡在这里）。
    # 用括号配对扫描，支持内部引号与方括号。
    cleaned = strip_etymology(block)

    m = re.search(r"[\u3400-\u4dbf\u4e00-\u9fff〈〔\[]", cleaned)
    if m:
        fr = cleaned[:m.start()].strip(" .;:，、")
        zh_rest = cleaned[m.start():].strip()
    else:
        fr = cleaned.strip(" .;:")
        zh_rest = ""

    zh = ""
    ex = ""
    if zh_rest:
        # 中文对应词到第一个中文冒号/英文冒号为止
        mc = re.search(r"[:：]", zh_rest)
        if mc:
            zh = zh_rest[:mc.start()].strip()
            ex = zh_rest[mc.end():].strip()
        else:
            # 没有冒号：中文只取到出现拉丁字母为止
            ml = re.search(r"[A-Za-zÀ-ÿ]", zh_rest)
            if ml:
                zh = zh_rest[:ml.start()].strip()
                ex = zh_rest[ml.start():].strip()
            else:
                zh = zh_rest.strip()

    # 去掉领域标记，单独留存
    domains = []
    for dm in DOMAIN_RE.finditer(block):
        d = (dm.group(1) or dm.group(2) or "").strip()
        if d:
            domains.append(d)

    zh = zh.strip(" 　.;,，、")
    fr = fr.strip()

    # 中文侧只应包含中文与词典标记。若混入成段法语，说明切分点选错了
    # （实测 876 条，如 "阿》Recueil des actes et des paroles..."）。
    # 处理：在第一个「长得像法语词」的位置截断。
    if zh:
        m2 = re.search(r"[A-Za-zÀ-ÿ]{4,}", zh)
        if m2:
            zh = zh[:m2.start()]
        # 去掉残缺的语域标记尾巴（「阿》」里的 》，「英》」里的 英》）
        zh = re.sub(r"^[）)\]】》〉〕]+\s*", "", zh)
        zh = re.sub(r"^[书旧俗古方文口诗法医史乐化]{1,2}[》〉〕]", "", zh)
        zh = zh.strip(" 　.;,，、")

    # 中文侧若以「[」开头，那是音标或注音被切过来了，不是释义。
    if zh.startswith("[") or zh.startswith("［"):
        zh = ""
    # 中文侧若全是符号或只有 1 个字符，丢
    if zh and len(zh) < 2:
        zh = ""
    # 只有中文才保留
    if zh and not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", zh):
        zh = ""

    if not fr and not zh:
        return None
    return {"fr": fr, "zh": zh, "ex": ex[:200], "dom": domains}


def main():
    D = json.load(io.open(SRC, encoding="utf-8"))
    sys.stderr.write("拉鲁斯条目 %d\n" % len(D))

    # 同一词头可能有多条（1. beau / 2. beau，1. livre / 2. livre / 3. livre）。
    # 这些是**同形异义词**（adj. beau 与 n.m. le beau；n.m. 书 与 n.f. 古斤），
    # 必须按编号顺序合并，不能只留一条——早期版本用 dict 覆盖，结果
    # livre 只剩「货币」义，「书」的义项全丢了。
    merged = collections.OrderedDict()

    def sort_key(r):
        h = (r.get("headword") or "")
        m = re.match(r"^(\d+)\.", h)
        return int(m.group(1)) if m else 0

    for r in sorted(D, key=sort_key):
        head = NUM_PREFIX.sub("", (r.get("headword") or "").strip())
        if not head:
            continue
        text = r.get("text") or ""
        if not text:
            continue

        key = head.lower()
        rec = merged.setdefault(key, {"h": head, "s": [], "pos": [], "ipa": ""})

        for g in split_pos_groups(text):
            pos, gipa, senses = parse_group(g)
            if gipa and not rec["ipa"]:
                rec["ipa"] = gipa
            if pos and pos not in rec["pos"]:
                rec["pos"].append(pos)
            for s in senses:
                s["pos"] = pos or s.get("pos", "")
                rec["s"].append(s)

    out = [r for r in merged.values() if r["s"]]

    stats = {"with_zh": 0, "with_pos": 0, "with_ipa": 0, "entries": len(out)}
    total_senses = 0
    for r in out:
        if any(s["zh"] for s in r["s"]):
            stats["with_zh"] += 1
        if r["pos"]:
            stats["with_pos"] += 1
        if r["ipa"]:
            stats["with_ipa"] += 1
        total_senses += len(r["s"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("解析出 %d 个词条 -> %s" % (len(out), OUT))
    print("  义项总数 %d" % total_senses)
    print("  带中文释义 %d（%.1f%%）"
          % (stats["with_zh"], 100 * stats["with_zh"] / max(1, stats["entries"])))
    print("  带词性 %d" % stats["with_pos"])
    print("  带音标 %d" % stats["with_ipa"])

    print("\n抽样：")
    by = {r["h"]: r for r in out}
    for w in ("maison", "beau", "eau", "livre", "manger", "grand", "nation"):
        r = by.get(w)
        if not r:
            print("  %-8s 未收录" % w)
            continue
        print("  【%s】pos=%s ipa=%s 义项 %d"
              % (w, "/".join(r.get("pos", [])), r.get("ipa", ""), len(r["s"])))
        for s in r["s"][:3]:
            print("     [%s] %s | 中：%s"
                  % (s["pos"], s["fr"][:52], s["zh"]))


if __name__ == "__main__":
    main()
