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

    # 清空所有旧例句。
    # 不能「在旧例句后面追加」——旧库里可能残留病句，
    # 追加会让病句活下来（实测：清空前 16,169 条病句）。
    # 例句一律以本次传入的 examples 文件为准。
    for e in ZF:
        e[6] = ""

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

                # 每词最多用例句数。
                #   存 1 句：58,358 词 → 约 28 MB
                #   存 2 句：约 45 MB（可接受，且能展示不同句式）
                # 取 2：既保证内容厚度，又不让首屏加载明显变慢。
                ex = e[6]
                if not ex:
                    cur = []
                elif isinstance(ex[0], list):
                    cur = ex
                else:
                    cur = [ex]          # 旧的单条结构 -> 包成列表

                if len(cur) >= MAX_PER_HEAD:
                    continue
                if not cur:
                    cur = []

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
                item = [d.get("zh_sent", ""), d.get("fr", ""),
                        d.get("fr_ipa", ""), lia, marked]

                # 去重：同一句不重复加
                if any(x[0] == item[0] for x in cur if isinstance(x, list)):
                    continue
                e[6] = cur + [item]
                attached += 1

    sys.stderr.write("例句 %d 條，掛上 %d 條\n" % (n_ex, attached))

    payload = json.dumps(ZF, ensure_ascii=False, separators=(",", ":"))
    with io.open(SRC, "w", encoding="utf-8") as f:
        f.write("window.ZF=" + payload + ";\n")
    print("寫回 %s（%.1f MB）" % (SRC, len(payload.encode("utf-8")) / 1048576))

    # 统计：e[6] 可能是单条 [zh,fr,ipa,lia,marked] 或是多条的 [[...],[...]]
    def norm_list(ex):
        if not ex:
            return []
        if isinstance(ex[0], list):
            return ex
        return [ex]

    with_ex = sum(1 for e in ZF if e[6])
    with_lia = 0
    n_lia = 0
    types = {}
    n_items = 0
    for e in ZF:
        for one in norm_list(e[6]):
            n_items += 1
            if len(one) > 3 and one[3]:
                with_lia += 1
                n_lia += len(one[3])
                for L in one[3]:
                    types[L["type"]] = types.get(L["type"], 0) + 1
    print("帶例句 %d / %d（%.1f%%），共 %d 條"
          % (with_ex, len(ZF), 100 * with_ex / max(1, len(ZF)), n_items))
    print("帶聯誦 %d 條，共 %d 處 %s" % (with_lia, n_lia, types))


if __name__ == "__main__":
    main()