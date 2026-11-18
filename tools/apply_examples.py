#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_examples.py — 把例句（含音标与联诵）写回主词库

输入：
  data/cache/examples_fr_ipa.jsonl   attach_example_ipa.py 产出
  app/zhfr.js                        主词库

输出：
  app/zhfr.js   第 7 字段（index 6）填为 [中文句, 法语句, 法语音标, 联诵数组]

字段规模控制：
  联诵数组只保留必要字段（i/type/phon/at），丢掉 reason 与冗长说明，
  否则 11 万条例句会让词库膨胀 30% 以上。

    python tools/apply_examples.py
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
EX = os.path.join(ROOT, "data", "cache", "examples_fr_ipa.jsonl")
MAX_PER_HEAD = 2          # 每个词头最多 2 条例句


def main():
    if not os.path.exists(SRC):
        sys.stderr.write("缺 %s\n" % SRC)
        raise SystemExit(1)

    src = io.open(SRC, encoding="utf-8").read()
    m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
    ZF = json.loads(m.group(1))
    sys.stderr.write("詞庫 %d 條\n" % len(ZF))

    by_simp = {}
    for i, e in enumerate(ZF):
        by_simp.setdefault(e[1], i)

    n_ex = 0
    attached = 0
    if os.path.exists(EX):
        with io.open(EX, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                n_ex += 1
                head = d.get("zh")
                if head not in by_simp:
                    continue
                i = by_simp[head]
                e = ZF[i]
                if e[6]:                       # 已有例句，跳过（每词一条）
                    continue
                # 精简联诵：只留渲染必需字段
                lia = []
                for L in (d.get("liaisons") or []):
                    lia.append({
                        "i": L.get("i"),
                        "type": L.get("type"),
                        "phon": L.get("phon", ""),
                        "at": L.get("at", ""),
                    })
                # 第 5 位存「联诵已内联标记」的句子与音标：
                #   fr  Ceci est‿un livre.
                #   ipa səsi ɛst‿œ̃ livʁ
                # 这样前端直接渲染即可，不必再算一遍联诵位置。
                marked = None
                if d.get("fr_marked") or d.get("ipa_marked"):
                    marked = {
                        "fr": d.get("fr_marked", ""),
                        "ipa": d.get("ipa_marked", ""),
                    }
                e[6] = [d.get("zh_sent", ""), d.get("fr", ""),
                        d.get("fr_ipa", ""), lia, marked]
                attached += 1

    sys.stderr.write("例句 %d 條，掛上 %d 條\n" % (n_ex, attached))

    payload = json.dumps(ZF, ensure_ascii=False, separators=(",", ":"))
    with io.open(SRC, "w", encoding="utf-8") as f:
        f.write("window.ZF=" + payload + ";\n")
    print("寫回 %s（%.1f MB）" % (SRC, len(payload.encode("utf-8")) / 1048576))

    # 统计
    with_ex = sum(1 for e in ZF if e[6])
    with_lia = sum(1 for e in ZF if e[6] and len(e[6][3]) > 0)
    n_lia = sum(len(e[6][3]) for e in ZF if e[6])
    types = {}
    for e in ZF:
        if not e[6]:
            continue
        for L in e[6][3]:
            types[L["type"]] = types.get(L["type"], 0) + 1
    print("帶例句 %d / %d（%.1f%%）" % (with_ex, len(ZF), 100 * with_ex / max(1, len(ZF))))
    print("帶聯誦 %d 條，共 %d 處 %s" % (with_lia, n_lia, types))


if __name__ == "__main__":
    main()