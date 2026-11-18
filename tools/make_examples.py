#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_examples.py — 中文例句 → Index-Translate → 法语译文

嚴格約束（紅線 R1/R2/R4）：
  1. 法語譯文**只能**來自 Index-Translate 免費公共網關，經 guard.py 發出；
  2. 不調用任何其他翻譯服務，不讀本機 API Key；
  3. AI 不自行生成譯文——腳本只做「發請求 + 校驗返回」，沒有任何本地生成分支；
  4. 譯文與原句行數必須一一對應，不對應的整批作廢（不猜、不補）。

輸入：
  漢南歸檔的 examples.json 漢文側（114,601 條），或自備 JSONL
    {"<詞頭>": ["<中文例句>", "<原譯文>"], ...}

輸出（續跑）：
  data/cache/examples_fr.jsonl
    {"zh":"詞頭","zh_sent":"中文句","fr":"法語句","src":"index-translate","ts":...}

    python tools/make_examples.py --limit 100          # 試跑
    python tools/make_examples.py                      # 全量
"""
import argparse
import concurrent.futures as cf
import io
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from guard import post_chat, assert_endpoint          # noqa: E402

OUT = os.path.join(ROOT, "data", "cache", "examples_fr.jsonl")

# 漢南歸檔的例句池（漢文側）
HANAN = os.path.normpath(os.path.join(
    ROOT, "..", "..", "..", "2026-11-7 汉南辞典", "02_数据管线", "产出", "examples.json"))
HANAN_APP = os.path.normpath(os.path.join(
    ROOT, "..", "..", "..", "2026-11-7 汉南辞典", "01_源码", "hanviet-app", "data", "examples.json"))

MAX_FAIL_STREAK = 12

PROMPT = """请把下面每一行中文句子翻译成地道、自然的现代法语。
要求：
1. 严格一行对一行，输出行数与输入完全相同，不合并、不拆分、不增删。
2. 只输出法语译文，不要编号、不要解释、不要引号、不要 markdown 代码块。
3. 使用标准书面法语，避免口语缩写（不写 j'sais、y a）。
4. 保留原句的标点与语气（疑问句用 ?，感叹句用 !）。
5. 若某行无法翻译，该行留空，不要编造内容。

输出格式：{"s": ["<译文1>", "<译文2>", ...]}

输入：
"""


def load_source(path):
    """读例句池，返回 [(词头, 中文句)]。

    支持两种格式：
      examples.json   {"<词头>": ["<中文句>", "<译文>"], ...}
      corpus_zh.jsonl 每行 {"zh":..,"s":..,"src":..}
    """
    pairs = []
    seen = set()
    if not os.path.exists(path):
        return pairs

    def accept(zh_head, s):
        s = str(s or "").strip()
        if not s or s in seen:
            return
        if zh_head not in s:
            return
        if len(zh_head) > 6:
            return
        if len(s) < 4 or len(s) > 45:
            return
        if re.search(r"[A-Za-z\u0600-\u06FF]", s):
            return
        if re.search(r"https?://|www\.", s):
            return
        seen.add(s)
        pairs.append((zh_head, s))

    if path.endswith(".jsonl"):
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                accept(d.get("zh", ""), d.get("s", ""))
        return pairs

    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    for zh_head, v in data.items():
        if isinstance(v, list) and v:
            accept(zh_head, v[0])
    return pairs


def parse_lines(raw, n):
    """解析模型返回。优先按 {"s":[...]} 位置数组，退回按行切。

    只用 Index-Translate 的返回，不做任何"补全"。
    """
    if not raw:
        return None
    t = raw.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)

    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        try:
            d = json.loads(t[i:j + 1])
            arr = d.get("s")
            if isinstance(arr, list) and len(arr) == n:
                return [str(x).strip() for x in arr]
        except Exception:
            pass

    lines = [l.strip() for l in t.split("\n") if l.strip()]
    if len(lines) == n:
        return lines
    return None


def valid_fr(s, zh_sent=""):
    """法语译文的基本合法性校验（不是质量校验）。

    关键：**生僻字译文要放行**。
      「㑇这个字现在已经很少用了。」的法语译文是
        Le caractère « 㑇 » est aujourd'hui très peu utilisé.
      里面本来就该保留「㑇」这个字——谚文语境里引用汉字是完全正常的。
      早期版本一律判「含中文=非法」，导致 2,000 多条生僻字例句全部作废、
      整批重试到熔断（实测连续 12 批失败）。
    """
    if not s:
        return False
    if len(s) > 320:
        return False
    if not re.search(r"[A-Za-zÀ-ÿ]", s):
        return False

    # 译文里出现的汉字，如果原句里也有，那是「引用原字」，合法
    cjk_in_out = set(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", s))
    if not cjk_in_out:
        return True
    cjk_in_src = set(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", zh_sent))
    # 全都是原句里出现过的字 -> 允许；出现原句没有的汉字 -> 说明模型没翻译干净
    return cjk_in_out.issubset(cjk_in_src)


def work(batch):
    """翻译一批。返回 (batch, out_list, err)"""
    zh_sents = [s for _, s in batch]
    payload = "\n".join("%d. %s" % (k + 1, s) for k, s in enumerate(zh_sents))
    # 提示里带编号便于对齐，但要求输出不带编号
    prompt = PROMPT + payload

    for attempt in range(2):
        raw = post_chat(prompt, max_tokens=3000, temperature=0.1,
                        audit_tag="examples")
        arr = parse_lines(raw, len(zh_sents))
        if arr:
            out = []
            ok = True
            for (zh_head, zh_s), fr in zip(batch, arr):
                fr = fr.strip()
                if not valid_fr(fr, zh_s):
                    ok = False
                    break
                out.append({"zh": zh_head, "zh_sent": zh_s, "fr": fr,
                            "src": "index-translate", "ts": int(time.time())})
            if ok and out:
                return batch, out, None
        time.sleep(1.2 * (attempt + 1))
    return batch, [], "batch failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    # 默认值来自 tools/bench_batch.py 与 bench_concurrency.py 的实测：
    #   批 16 是单次调用的最优档（批 24/32 网关排队，每句更慢；批 48 直接 504）
    #   并发 24 时吞吐 51.88 句/s，成功率 100%
    #   汉南当年用批 8 / 并发 5，约 6 句/s——差 8 倍
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()

    assert_endpoint()

    src_path = args.source
    if not src_path:
        # 优先用语料池（40 万句），退回汉南池（11 万句）
        for p in (os.path.join(ROOT, "data", "corpus_zh.jsonl"), HANAN, HANAN_APP):
            if os.path.exists(p):
                src_path = p
                break
    if not src_path or not os.path.exists(src_path):
        sys.stderr.write("找不到例句源。用 --source 指定 examples.json\n")
        raise SystemExit(1)

    sys.stderr.write("例句源：%s\n" % src_path)
    pairs = load_source(src_path)
    sys.stderr.write("可用中文句 %d\n" % len(pairs))

    done = set()
    if os.path.exists(args.out):
        with io.open(args.out, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["zh_sent"])
                except Exception:
                    pass
    todo = [x for x in pairs if x[1] not in done]
    if args.limit:
        todo = todo[:args.limit]
    sys.stderr.write("已完成 %d，待译 %d\n" % (len(done), len(todo)))
    if not todo:
        return

    batches = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fout = io.open(args.out, "a", encoding="utf-8")

    ok = bad = streak = 0
    t0 = time.time()
    it = iter(batches)
    pending = set()
    lane = max(2, args.workers)

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        def fill():
            while len(pending) < lane * 2:
                try:
                    pending.add(ex.submit(work, next(it)))
                except StopIteration:
                    return

        fill()
        i = 0
        while pending:
            finished, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fu in finished:
                pending.discard(fu)
                try:
                    batch, out, err = fu.result()
                except Exception as e:
                    batch, out, err = [], [], str(e)[:60]
                i += 1
                if err:
                    bad += len(batch)
                    streak += 1
                else:
                    streak = 0
                    for r in out:
                        fout.write(json.dumps(r, ensure_ascii=False) + "\n")
                        ok += 1
                fout.flush()
                if i % 10 == 0:
                    dt = max(1, time.time() - t0)
                    sys.stderr.write("[%d] ok=%d bad=%d %.2f 句/s\n"
                                     % (i, ok, bad, ok / dt))
                if streak >= MAX_FAIL_STREAK:
                    sys.stderr.write("连续 %d 批失败，提前停止（缓存可续跑）\n" % streak)
                    for x in pending:
                        x.cancel()
                    pending.clear()
                    break
            if streak >= MAX_FAIL_STREAK:
                break
            fill()

    fout.close()
    sys.stderr.write("完成 ok=%d bad=%d 耗时 %.0fs\n" % (ok, bad, time.time() - t0))


if __name__ == "__main__":
    main()