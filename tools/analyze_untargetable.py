#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_untargetable.py — 区分「该有例句但缺」与「本就造不出例句」

问题：
  覆盖率停在 88%，缺口 6,846 条。但抽样一看，缺的大多是：
    㑇 㑩 䍃 䓛  ｜ 生僻字（CJK 扩展区）
    両 亀 乗     ｜ 日本汉字（新字体）
    Meitnérium  ｜ 化学元素名
    乂 乇       ｜ 文言/度量单位

  这些词在现代汉语里根本不单独成词，造「他每天買一個㑇」这种句子
  是做假数据，不是做词典。汉南在已知限制里也承认了这一点。

正确做法：
  把「例句覆盖率」算在两个分母上：
    分母 A：全部词条            —— 真实但会被人为拉低
    分母 B：可造例句的词条      —— 更能反映工艺水平
  两个数都要报，不挑好看的那个。

    python tools/analyze_untargetable.py
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
SRC = os.path.join(ROOT, "app", "zhfr.js")
OUT = os.path.join(ROOT, "data", "untargetable.tsv")

# CJK 基本区之外的扩展区：生僻字，现代汉语不单独成词
EXT_BLOCKS = [
    (0x3400, 0x4DBF),    # 扩展 A
    (0x20000, 0x2A6DF),  # 扩展 B
    (0x2A700, 0x2B73F),  # 扩展 C
    (0x2B740, 0x2B81F),  # 扩展 D
    (0x2B820, 0x2CEAF),  # 扩展 E
    (0x2CEB0, 0x2EBEF),  # 扩展 F
    (0x30000, 0x3134F),  # 扩展 G
    (0xF900, 0xFAFF),    # 兼容汉字
]

# 日本汉字（新字体/略字）：中文不用的写法
JAPANESE = set("両亀乗仏徳恵絵駅円気県戸歳浜芸広対鉄転売発楽覧竜")

# 计量/单位/化学元素/专业术语的典型标志
PROFESSIONAL = re.compile(
    r"(Meit|chrysène|Torr|Tael|rutherfordium|darmstadtium|livermorium|"
    r"bohrium|hassium|dubnium|seaborgium|mendelevium|nobelium|lawrencium|"
    r"isotope|numération|radical|bopomofo)", re.I)

# 文言/古语标注
ARCHAIC = re.compile(r"\((arch|anc|vx|class|lit|dial)\.?\)|古|文言", re.I)


def is_ext(cp):
    for a, b in EXT_BLOCKS:
        if a <= cp <= b:
            return True
    return False


def classify(e):
    """返回 (类别, 原因)

    判斷標準来自实际抽样，不是凭感觉：
      单字在 CJK 基本区之外（扩展 A/B/C…）-> 生僻字，现代汉语不单独成词
      词头含拉丁字母或数字（C盘 / P波 / 5瓶 / T裇）-> 无法用中文模板造句
      义项是元素名/单位/学名 -> 专业术语
      义项标注 arch/vx -> 文言
      其余单字/多字 -> 可造例句
    """
    head = e[1]
    sense = e[3] or ""

    # 含拉丁字母或数字：中文句子里的「C盘」「K粉」「5瓶」这类
    # 模板造句会造出病句，需要专门处理（或本就只作词条展示）
    if re.search(r"[A-Za-z0-9]", head):
        return "untargetable", "含拉丁字母/数字"

    if len(head) > 1:
        return "targetable", ""

    cp = ord(head)
    if is_ext(cp):
        return "untargetable", "生僻字（CJK 扩展区）"
    if head in JAPANESE:
        return "untargetable", "日本汉字"
    if PROFESSIONAL.search(sense):
        return "untargetable", "专业术语/元素名/单位"
    if ARCHAIC.search(sense):
        return "untargetable", "文言/古语"
    return "targetable", ""


def main():
    src = io.open(SRC, encoding="utf-8").read()
    ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S).group(1))

    have = [e for e in ZF if e[6]]
    miss = [e for e in ZF if not e[6]]

    cats = {}
    rows = []
    miss_targetable = []
    for e in miss:
        cat, why = classify(e)
        cats[why or "可造例句"] = cats.get(why or "可造例句", 0) + 1
        rows.append((e[1], cat, why))
        if cat == "targetable":
            miss_targetable.append(e)

    total = len(ZF)
    n_have = len(have)
    n_target_total = total - (len(miss) - len(miss_targetable))

    print("=" * 64)
    print("例句覆盖率分析")
    print("=" * 64)
    print("全部词条            %6d" % total)
    print("已有例句            %6d" % n_have)
    print("缺口                %6d" % len(miss))
    print()
    print("缺口构成：")
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        print("  %-28s %6d" % (k, v))
    print()
    print("分母 A（全部词条）       覆盖 %.2f%%  = %d / %d"
          % (100 * n_have / total, n_have, total))
    print("分母 B（可造例句的词条） 覆盖 %.2f%%  = %d / %d"
          % (100 * n_have / n_target_total, n_have, n_target_total))
    print()
    print("还差 %d 条可造例句的词条才能让分母 B 到 95%%"
          % max(0, int(n_target_total * 0.95) - n_have))

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("词头\t类别\t原因\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    print("\n明细 -> %s" % OUT)


if __name__ == "__main__":
    main()