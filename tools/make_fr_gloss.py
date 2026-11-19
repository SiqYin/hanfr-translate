#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fr_gloss.py — 用免费 AI 源为缺中文释义的法语词补释义

背景：
  拉鲁斯双解只收 33,597 个词条，法语义项 68,637 条。
  但我们的法语词表有 43,516 个词，其中 9,352 个没有中文释义
  （9,094 个连义项都没有——它们来自 WOLF/构词法，只有语义关系）。

  用户要求：汉法词典不能一堆词没中文释义，必须全部补上。

做法：
  1. 有法语释义但缺中文 -> 翻译该释义（质量最好，忠于原词典）
  2. 连法语释义都没有 -> 让模型按词 + 词性生成简短释义
  3. 结果写缓存，可续跑；逐条校验，不合格的重试

通道：只走 guard.py 允许的 Index-Translate 免费网关。
     不读任何 API Key，不碰任何付费端点。

    python tools/make_fr_gloss.py            # 续跑
    python tools/make_fr_gloss.py --limit 500
    python tools/make_fr_gloss.py --dry-run
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from guard import post_chat, assert_endpoint  # noqa: E402

DETAIL = os.path.join(ROOT, "app", "frdetail.js")
CACHE = os.path.join(ROOT, "data", "cache", "fr_gloss.jsonl")
LOCK = threading.Lock()

# 翻译已有法语释义 -> 汉语对应词
PROMPT_TRANS = (
    "你是法汉词典的编纂者，为中文读者编写释义。\n"
    "把下面每条法语释义压缩成简短的汉语对应词，像《法汉词典》那样。\n"
    "要求：\n"
    "1. 只输出译文，不要编号、不要解释。\n"
    "2. 名词给对应词（Assemblage de feuilles... -> 书,书本,书籍）；\n"
    "   形容词给「…的」；动词给「…；…」的对应动词。\n"
    "3. 不要照译成完整句子。\n"
    "4. 语域标记保留：FAM.→〈俗〉 LITT.→〈书〉 VX.→〈旧〉 POP.→〈民〉 "
    "ARG.→〈行〉 FIG.→〈转〉\n"
    "5. 领域标记用〔〕：DR.→〔法〕 MUS.→〔乐〕 MED.→〔医〕 BOT.→〔植〕 "
    "ZOOL.→〔动〕 CHIM.→〔化〕 MATH.→〔数〕 INFORM.→〔计〕\n"
    "6. 行数与输入一致。\n\n"
    "输出格式：{\"s\": [\"译文1\", \"译文2\"]}\n\n输入：\n"
)

# 没有法语释义时，按词 + 词性生成
PROMPT_GEN = (
    "你是法汉词典的编纂者。下面给出法语词及其词性，请写出简短的汉语释义，"
    "像《法汉词典》那样给对应词，不要解释词的含义、不要造句。\n"
    "要求：只输出释义，不要编号。名词给对应词；形容词给「…的」；"
    "动词给对应动词。若该词是专名（地名、人名、机构），"
    "输出「（专名）」加汉语通行译名。\n"
    "行数与输入一致。\n\n"
    "输出格式：{\"s\": [\"释义1\", \"释义2\"]}\n\n输入：\n"
)


def parse_s(raw, want):
    """多级容错解析，返回 list[str] 或 None。"""
    if not raw:
        return None
    t = raw.strip()

    j, k = t.find("{"), t.rfind("}")
    if j >= 0 and k > j:
        try:
            obj = json.loads(t[j:k + 1])
            arr = obj.get("s")
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr
                       if isinstance(x, (str, int, float))]
                if out:
                    return out
        except Exception:
            pass
        # 畸形 JSON：主数组后接了平级数组
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


CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def valid_gloss(g, src=""):
    """校验生成的汉语释义是否可用。

    「参见」类条目（源文形如 "2. automobile"、"pl. → bail"）不该翻译——
    它们只是指向另一个词，原文里没有真正的释义内容。
    这类要靠 sense_refs 处理，不该混进翻译队列。
    """
    if not g:
        return False
    g = g.strip()
    if len(g) > 60:
        return False

    # 译文里残留编号（"2. 丑闻"）说明源文的编号没剥干净，或模型把编号当内容
    if re.match(r"^\d+[\.\)]\s*", g):
        return False
    # 译文里残留法语原文
    if re.search(r"[A-Za-zÀ-ÿ]{4,}", g):
        return False
    # 至少要有汉字，否则等于没翻译
    if not CJK.search(g):
        return False
    if re.fullmatch(r"[\s\W\dA-Za-zÀ-ÿ]+", g):
        return False
    return True


# 「参见」类源文特征：带编号、带箭头、只有词性缩写
REF_SRC = re.compile(
    r"^\s*(?:\d+\.\s*)?[\w\s,'’\-]*?(?:→|➔)\s*\S+\s*$|"
    r"^\s*\d+\.\s*[a-zà-ÿ]+\s*$|"
    r"^\s*(?:pl|m|f|adj|n|v|dém|poss|pers|relat)\b[\w\s.,]*→", re.I)


def is_ref_src(src):
    """判断源文是不是「参见」而非真释义。"""
    if not src:
        return False
    s = src.strip()
    if "→" in s or "➔" in s:
        return True
    if re.match(r"^\d+\.\s*[a-zà-ÿ]+\s*$", s):
        return True
    return False


def load_cache():
    done = {}
    if not os.path.exists(CACHE):
        return done
    with io.open(CACHE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            done[d["k"]] = d
    return done


def append_cache(rows):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with io.open(CACHE, "a", encoding="utf-8") as f:
        for d in rows:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_targets():
    s = io.open(DETAIL, encoding="utf-8").read()
    D = json.loads(re.search(r"window\.FRDETAIL=(\{.*\});", s, re.S).group(1))

    # 需要补的词，按类型分组
    trans_jobs = []   # 有法语释义，缺中文
    gen_jobs = []     # 连法语释义都没有
    sense_refs = []   # 「→ 某词」参见类，不需翻译

    for w, rec in D.items():
        senses = rec.get("s") or []
        if any(x.get("zh") for x in senses):
            continue
        pos = "/".join(rec.get("pos") or []) or ""
        if senses:
            for i, sn in enumerate(senses):
                fr = (sn.get("fr") or "").strip()
                if not fr or sn.get("zh"):
                    continue
                # 「参见」类空释义：拉鲁斯里写的就是 "→ abrogatif"
                # 这类不该让模型翻译，应指向原词条。
                ref = re.match(r"^[→➔]\s*([a-zà-ÿœæç'’-]+)", fr)
                if not ref:
                    # 形如 "2. automobile" / "pl. → bail" / "→ 2. canette"
                    m2 = re.search(r"[→➔]\s*(?:\d+\.\s*)?([a-zà-ÿœæç'’-]+)", fr)
                    if m2 or re.match(r"^\d+\.\s*[a-zà-ÿ]+\s*$", fr):
                        tgt = m2.group(1) if m2 else re.sub(r"^\d+\.\s*", "", fr).strip()
                        sense_refs.append({"k": "r|%s|%d" % (w, i), "w": w,
                                           "target": tgt})
                        continue
                if ref:
                    sense_refs.append({"k": "r|%s|%d" % (w, i), "w": w,
                                       "target": ref.group(1)})
                    continue
                trans_jobs.append({"k": "t|%s|%d" % (w, i), "w": w,
                                   "pos": sn.get("pos") or pos, "src": fr})
        else:
            gen_jobs.append({"k": "g|%s" % w, "w": w, "pos": pos, "src": ""})

    return trans_jobs, gen_jobs, sense_refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    assert_endpoint()

    sys.stderr.write("扫描待补词条...\n")
    trans_jobs, gen_jobs, sense_refs = load_targets()
    sys.stderr.write("  待翻译释义 %d 条\n" % len(trans_jobs))
    sys.stderr.write("  待生成释义 %d 词\n" % len(gen_jobs))
    sys.stderr.write("  参见类（不翻译）%d 条\n" % len(sense_refs))

    cache = load_cache()
    sys.stderr.write("  缓存已有 %d 条\n" % len(cache))

    todo_t = [j for j in trans_jobs if j["k"] not in cache]
    todo_g = [j for j in gen_jobs if j["k"] not in cache]
    sys.stderr.write("  仍待处理：翻译 %d，生成 %d\n"
                     % (len(todo_t), len(todo_g)))

    if args.limit:
        todo_t = todo_t[:args.limit]
        todo_g = todo_g[:args.limit]

    all_todo = [("t", j) for j in todo_t] + [("g", j) for j in todo_g]
    if args.dry_run:
        print("dry-run：将处理 %d 条" % len(all_todo))
        for kind, j in all_todo[:10]:
            print("  [%s] %-16s %s" % (kind, j["w"], (j["src"] or "")[:50]))
        return

    if not all_todo:
        print("没有待处理条目")
        return

    ok = bad = 0
    fail_streak = 0
    t0 = time.time()
    nbatch = (len(all_todo) + args.batch - 1) // args.batch

    def run_batch(bi):
        nonlocal ok, bad, fail_streak
        chunk = all_todo[bi * args.batch:(bi + 1) * args.batch]
        if not chunk:
            return
        kinds = [c[0] for c in chunk]
        # 同一批只处理同类，避免提示词混用
        if len(set(kinds)) > 1:
            chunk = [(kinds[0], j) for k, j in chunk if k == kinds[0]]
        kind = chunk[0][0]

        if kind == "t":
            payload = "\n".join("%d. %s" % (i + 1, c[1]["src"][:220])
                                for i, c in enumerate(chunk))
            prompt = PROMPT_TRANS
        else:
            payload = "\n".join("%d. %s [%s]" % (i + 1, c[1]["w"], c[1]["pos"] or "?")
                                for i, c in enumerate(chunk))
            prompt = PROMPT_GEN

        raw = post_chat(prompt + payload, max_tokens=1200, temperature=0.1,
                        audit_tag="frgloss")
        out = parse_s(raw, len(chunk))

        rows = []
        if out and len(out) >= len(chunk):
            for (k, j), g in zip(chunk, out):
                if valid_gloss(g, j["src"]):
                    rows.append({"k": j["k"], "w": j["w"], "zh": g.strip(),
                                 "src": (j["src"] or "")[:150]})
        with LOCK:
            if rows:
                append_cache(rows)
                ok += len(rows)
                fail_streak = 0
            else:
                bad += len(chunk)
                fail_streak += 1
            done = ok + bad
            if (bi + 1) % 10 == 0:
                rate = done / max(0.1, time.time() - t0)
                sys.stderr.write("[%d/%d] ok=%d bad=%d %.2f 条/s\n"
                                 % (bi + 1, nbatch, ok, bad, rate))

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_batch, i) for i in range(nbatch)]
        for f in futs:
            try:
                f.result()
            except Exception as e:
                sys.stderr.write("batch err: %s\n" % e)
            if fail_streak >= 12:
                sys.stderr.write("连续 12 批失败，提前停止（缓存可续跑）\n")
                break

    print("\n完成 ok=%d bad=%d 耗时 %ds" % (ok, bad, time.time() - t0))
    print("缓存：%s" % CACHE)


if __name__ == "__main__":
    main()
