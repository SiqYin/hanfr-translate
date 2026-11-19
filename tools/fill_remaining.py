#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fill_remaining.py — 补齐最后一批无释义的词

前面几轮之后只剩几十个词没有中文释义。这些是：
  - 参见类里目标词本身解析失败的（aulx -> ail，但 ail 的释义取坏了）
  - 缩写（aaa / cps / cqfd）
  - 极冷僻词（isopet / couros）

处理：直接按「词 + 词性 + 拉鲁斯的原始释义（若有）」让 AI 生成。

    python tools/fill_remaining.py
"""
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from guard import post_chat, assert_endpoint  # noqa: E402

DETAIL = os.path.join(ROOT, "app", "frdetail.js")
LAR = os.path.join(ROOT, "data", "larousse_senses.jsonl")
CACHE = os.path.join(ROOT, "data", "cache", "fr_gloss.jsonl")
REMAIN = os.path.join(ROOT, "data", "remaining_gloss.txt")

PROMPT = (
    "你是法汉词典的编纂者。下面给出法语词、词性，以及（若有）法语原释义。"
    "请写出简短的汉语释义，像《法汉词典》那样给对应词。\n"
    "只输出释义，不要编号、不要解释。名词给对应词，形容词给「…的」，"
    "动词给对应动词。若是缩写就给全称的汉语译名；若是专名给通行译名。\n"
    "行数与输入一致。\n\n"
    "输出格式：{\"s\": [\"释义1\", \"释义2\"]}\n\n输入：\n"
)

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def parse_s(raw, want):
    if not raw:
        return None
    t = raw.strip()
    j, k = t.find("{"), t.rfind("}")
    if j >= 0 and k > j:
        try:
            obj = json.loads(t[j:k + 1])
            arr = obj.get("s")
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr if isinstance(x, (str, int, float))]
                if out:
                    return out
        except Exception:
            pass
        frag = t[j:k + 1]
        strs = re.findall(r'"((?:[^"\\]|\\.)*)"', frag)
        vals = [s for s in strs if s != "s"]
        if len(vals) >= want:
            return vals[:want]
    lines = [l.strip().strip('",') for l in t.split("\n") if l.strip()]
    lines = [re.sub(r"^\d+[\.\)]\s*", "", l) for l in lines]
    lines = [l for l in lines if l and l not in ("{", "}", "[", "]")]
    if len(lines) >= want:
        return lines[:want]
    return None


def ok(g):
    if not g or len(g.strip()) > 60:
        return False
    if not CJK.search(g):
        return False
    if re.search(r"[A-Za-zÀ-ÿ]{4,}", g):
        return False
    return True


def main():
    assert_endpoint()

    s = io.open(DETAIL, encoding="utf-8").read()
    D = json.loads(re.search(r"window\.FRDETAIL=(\{.*\});", s, re.S).group(1))
    need = [w for w, r in D.items()
            if not any(x.get("zh") for x in (r.get("s") or []))]

    # 拉鲁斯原始释义（供参考）
    raw_def = {}
    if os.path.exists(LAR):
        with io.open(LAR, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                ds = [x.get("fr", "") for x in r["s"][:2] if x.get("fr")]
                if ds:
                    raw_def[r["h"].lower()] = " / ".join(ds)[:120]

    # 已有缓存里的
    done = set()
    if os.path.exists(CACHE):
        with io.open(CACHE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        done.add(json.loads(line)["k"])
                    except Exception:
                        pass
    need = [w for w in need if ("g|%s" % w) not in done]

    print("待补 %d 个词" % len(need))
    if not need:
        return

    BATCH = 6
    rows = []
    for bi in range(0, len(need), BATCH):
        chunk = need[bi:bi + BATCH]
        payload = "\n".join(
            "%d. %s [%s]%s" % (
                i + 1, w,
                "/".join(D[w].get("pos") or []) or "?",
                (" 原文：" + raw_def[w]) if w in raw_def else "")
            for i, w in enumerate(chunk))
        raw = post_chat(PROMPT + payload, max_tokens=900, temperature=0.1,
                        audit_tag="frglossfill")
        out = parse_s(raw, len(chunk))
        if out:
            for w, g in zip(chunk, out):
                if ok(g):
                    rows.append({"k": "g|%s" % w, "w": w, "zh": g.strip(),
                                 "src": raw_def.get(w, "")[:150]})
        time.sleep(0.4)

    if rows:
        with io.open(CACHE, "a", encoding="utf-8") as f:
            for d in rows:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print("补上 %d / %d" % (len(rows), len(need)))
    for d in rows[:15]:
        print("  %-18s -> %s" % (d["w"], d["zh"]))


if __name__ == "__main__":
    main()
