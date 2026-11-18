#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_corpus.py — 扩充中文例句池

为什么必须自己造：
  汉南的 examples.json 只有 114,601 句，全部拿来也就 11 万。
  要 30 万到 100 万句，必须有更大的中文句池。
  法语资源多、模型强，这是可以大幅超越汉南的领域。

来源优先级：
  1. 汉南 examples.json 的汉文侧（114,601 条，高质量，人工筛过）
  2. 汉南译文缓存里的中文侧（ex_zh_cache 等，可能有额外句子）
  3. 词库自身造句（高频词 × 句式模板，可控且保证覆盖）
  4. HSK / 现代汉语常用词表 + 模板

产出：data/corpus_zh.jsonl  {"zh":词头, "s":中文句, "src":来源}

    python tools/build_corpus.py
    python tools/build_corpus.py --target 400000
"""
import argparse
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
OUT = os.path.join(ROOT, "data", "corpus_zh.jsonl")

HANAN_DIR = os.path.normpath(os.path.join(ROOT, "..", "..", "..", "2026-11-7 汉南辞典"))
HANAN_EX = os.path.join(HANAN_DIR, "02_数据管线", "产出", "examples.json")
HANAN_APP_EX = os.path.join(HANAN_DIR, "01_源码", "hanviet-app", "data", "examples.json")
MODERN = os.path.join(ROOT, "data", "modern_chinese_words.tsv")
HSK = os.path.join(ROOT, "data", "hsk_all.tsv")

seen = set()
rows = []
stat = collections.Counter()


def add(zh_head, sent, src):
    sent = (sent or "").strip()
    if not sent or sent in seen:
        return False
    if zh_head not in sent:
        return False
    if len(sent) < 4 or len(sent) > 45:
        return False
    if re.search(r"[A-Za-z\u0600-\u06FF]", sent):
        return False
    if re.search(r"https?://|www\.", sent):
        return False
    # 过滤定义式、文言、非陈述句
    if re.search(r"是一种|是一类|指的是|通常指|是指|称为|叫做", sent):
        return False
    if re.search(r"之乎者也|曰|焉|矣哉", sent):
        return False
    seen.add(sent)
    rows.append({"zh": zh_head, "s": sent, "src": src})
    stat[src] += 1
    return True


# ---------------- 1. 汉南例句池 ----------------
def load_hanan():
    for p in (HANAN_EX, HANAN_APP_EX):
        if not os.path.exists(p):
            continue
        try:
            data = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for zh, v in data.items():
            if isinstance(v, list) and v:
                add(zh, str(v[0]), "hanan")
        sys.stderr.write("汉南池 %s：累计 %d\n" % (os.path.basename(p), len(rows)))
        return


# ---------------- 2. 词表 ----------------
def load_words():
    """返回 [(词, 频序)]，按常用度排序

    来源优先级：
      1. 词库本身的全部词头（zhfr.js）—— 最要紧：例句要挂到这些词上，
         只用外部词表会漏掉大量词库内部的词（实测漏了 5,700+ 条）
      2. HSK 词表
      3. 现代汉语常用词表
    """
    out = []

    # 1. 词库词头（最重要）
    zhfr = os.path.join(ROOT, "app", "zhfr.js")
    if os.path.exists(zhfr):
        try:
            src = io.open(zhfr, encoding="utf-8").read()
            m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
            if m:
                ZF = json.loads(m.group(1))
                for e in ZF:
                    w = e[1]
                    if w and len(w) <= 6:
                        out.append((w, 50000))     # 中等优先级
                sys.stderr.write("词库词头 %d\n" % len(out))
        except Exception as ex:
            sys.stderr.write("读词库失败：%s\n" % ex)

    if os.path.exists(HSK):
        for line in io.open(HSK, encoding="utf-8", errors="replace"):
            w = line.strip().split("\t")[0].strip()
            if w and len(w) <= 6 and re.match(r"^[\u4e00-\u9fff]+$", w):
                out.append((w, 1))
    if os.path.exists(MODERN):
        with io.open(MODERN, encoding="utf-8", errors="replace") as f:
            header = f.readline().rstrip("\n").split("\t")
            try:
                i_w, i_r = header.index("词语"), header.index("频序号")
            except ValueError:
                i_w, i_r = 0, 1
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) <= max(i_w, i_r):
                    continue
                w = p[i_w].strip()
                if not w or len(w) > 6:
                    continue
                if not re.match(r"^[\u4e00-\u9fff]+$", w):
                    continue
                try:
                    r = int(p[i_r])
                except ValueError:
                    r = 99999
                out.append((w, r))
    # 去重，保留最小频序
    best = {}
    for w, r in out:
        if w not in best or r < best[w]:
            best[w] = r
    return sorted(best.items(), key=lambda kv: kv[1])


# ---------------- 3. 句式模板 ----------------
# 造出的句子必须像人话。模板按词性粗略分组，避免「把书放进洗衣机」这种荒谬。
TEMPLATES = {
    "n": [
        "这张{w}很结实。", "我把{w}放在桌子上了。", "他买了一个新的{w}。",
        "这个{w}多少钱？", "请把{w}递给我。", "{w}在房间的角落里。",
        "她喜欢这个{w}。", "我们家的{w}坏了，需要修理。",
        "他把{w}送给了朋友。", "这个{w}看起来很不错。",
        "你能帮我拿下那个{w}吗？", "{w}放在哪儿了？",
        "这批{w}的质量很好。", "他每天都要用到{w}。",
        "我昨天在商店看到一个很漂亮的{w}。",
        "这个{w}比那个贵一点。", "孩子们在玩那个{w}。",
        "请把{w}擦干净。", "他把{w}从柜子里拿了出来。",
        "这个{w}已经用了很多年了。",
    ],
    "v": [
        "他每天{w}一个小时。", "你应该{w}得再仔细一点。",
        "我们一起{w}吧。", "她不想{w}。", "现在{w}还来得及。",
        "他们决定明天{w}。", "我昨天{w}了一整天。",
        "这件事必须{w}。", "他教我怎样{w}。", "你{w}得怎么样？",
        "我们{w}完就回家。", "她一直在{w}。", "别急着{w}。",
        "他{w}的时候很专注。", "我想{w}，但是没时间。",
        "他们{w}了很久才成功。", "你为什么不{w}呢？",
        "{w}之前要先准备好。", "他{w}得比我好。",
        "我们一起{w}了两个小时。",
    ],
    "a": [
        "今天的天气很{w}。", "这件衣服看起来很{w}。",
        "他家的院子特别{w}。", "这个想法很{w}。",
        "她的房间收拾得很{w}。", "这条路很{w}。",
        "那家餐厅的菜很{w}。", "他说话的语气很{w}。",
        "这个地方比以前{w}多了。", "孩子画得又{w}又生动。",
        "这个方案听起来很{w}。", "雨后的空气特别{w}。",
        "他的回答很{w}。", "这朵花开得真{w}。",
        "今天的天空特别{w}。", "她的字写得很{w}。",
        "这件家具看着很{w}。", "他今天心情很{w}。",
        "这部电影很{w}。", "山上的风景非常{w}。",
    ],
}


def guess_pos(w):
    """极粗的词性判断：只用于选模板，不追求准确。"""
    if re.search(r"(的|地|得)$", w):
        return "a"
    if re.search(r"(做|走|跑|吃|喝|看|说|想|来|去|买|卖|学|写|读|听|睡|起|开|关|放|拿|给|找|问|答|帮|等|用|玩|唱|跳|洗|擦|修|做)$", w):
        return "v"
    return "n"


# CJK 扩展区（生僻字）：现代汉语不单独成词，造例句只会得到病句
EXT_BLOCKS = [(0x3400, 0x4DBF), (0x20000, 0x2A6DF), (0x2A700, 0x2B73F),
              (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF), (0x2CEB0, 0x2EBEF),
              (0x30000, 0x3134F), (0xF900, 0xFAFF)]


def is_rare_char(ch):
    cp = ord(ch)
    for a, b in EXT_BLOCKS:
        if a <= cp <= b:
            return True
    return False


def targetable(w):
    """判断这个词能不能造出自然的现代汉语例句。

    不能造的：
      - 含拉丁字母/数字（C盘 / P波 / 5瓶）——模板造句必出病句
      - 单字且属于生僻扩展区（㑇 䍃）——现代汉语不单独用
    其余都能造。
    """
    if re.search(r"[A-Za-z0-9]", w):
        return False
    if len(w) == 1 and is_rare_char(w):
        return False
    return True


def generate(target, words):
    """用模板造句子，直到达到目标量"""
    sys.stderr.write("开始模板造句，目标 %d\n" % target)
    n0 = len(rows)
    wi = 0
    nw = len(words)
    if not nw:
        return
    skipped = 0
    while len(rows) < target and wi < nw * 20:
        w = words[wi % nw][0]
        wi += 1
        if not targetable(w):
            skipped += 1
            continue
        pos = guess_pos(w)
        tpls = TEMPLATES[pos]
        t = tpls[(wi // nw) % len(tpls)]
        add(w, t.replace("{w}", w), "template")
        if wi % 50000 == 0:
            sys.stderr.write("  %d / %d（跳过 %d 条不可造）\n"
                             % (len(rows), target, skipped))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=400000)
    args = ap.parse_args()

    load_hanan()
    words = load_words()
    sys.stderr.write("词表 %d 条\n" % len(words))

    if len(rows) < args.target:
        generate(args.target, words)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("总句数 %d -> %s" % (len(rows), OUT))
    for k, v in stat.most_common():
        print("  %-10s %7d" % (k, v))
    heads = len({r["zh"] for r in rows})
    print("覆盖词头 %d" % heads)


if __name__ == "__main__":
    main()