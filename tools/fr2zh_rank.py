#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fr2zh_rank.py — 用法→中候選做 AI 精排（只排序，不生成）

嚴格照漢南 ai_vi2zh.py 的定位：
  **AI 只排序，不產出譯文。** 返回值必須是輸入候選的子集，多出任何新詞即判為失敗。

為什麼不能靠啟發式：
  chien 反演出「犬、狗」，médecin 反演出「大、医生」，vin 反演出「杯中物、酒」。
  中文詞頻表解決不了這類問題——「犬」頻次確實高，但現代漢語說「狗」；
  「大」是高頻字，但跟 médecin 無關。這需要語義判斷，正是模型擅長且**可驗證**
  （排序結果是候選子集，可以逐項核對）的部分。

紅線：
  - 端點只走 guard.py（Index-Translate）；
  - 返回項必須在候選列表內，否則整批作廢；
  - 失敗批不落緩存，保證續跑乾淨（漢南教訓：空名單會永久污染）。

    python tools/fr2zh_rank.py --limit 200     # 試跑
    python tools/fr2zh_rank.py                 # 全量
"""
import argparse
import collections
import io
import json
import os
import queue
import re
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from guard import post_chat, assert_endpoint          # noqa: E402

SRC = os.path.join(ROOT, "app", "zhfr.js")
CACHE = os.path.join(ROOT, "data", "fr2zh_rank_cache.jsonl")
FUNC = os.path.join(ROOT, "data", "fr_func_words.tsv")

MAX_GLOSS = 4
MAX_TOKENS = 4
BATCH = 8            # 批 30 會觸發網關 504（漢南實測）
WORKERS = 5

CJK = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")

# 文言/生僻單字：即使出現在候選裡也不該被選為現代漢語對應
# 這份表是從實際跑出來的壞結果裡累積的，不是憑空列的
BAD_SINGLE = set("丌斯伊啓炁叟倭佤傣円邑廬焉矣哉乎兮者之其此彼何莫弗毋勿欤耶尔汝吾予余曰云蓋夫且若雖則即而所恁")
# 明確的文言/古舊詞，禁止整詞輸出
BAD_WORDS = set("""
春秋 華里 東夷 齊國 佬 爾 汝 吾 予 之乎者也 嗚呼哀哉
""".split())

ZH_RANK = {}


def load_zh_rank():
    """載入中文常用詞表，用於判定候選是否為現代常用詞。"""
    path = os.path.join(ROOT, "data", "modern_chinese_words.tsv")
    if not os.path.exists(path):
        alt = os.path.normpath(os.path.join(
            ROOT, "..", "..", "..", "2026-11-7 汉南辞典", "01_源码", "hanviet-app",
            "data", "modern_chinese_words.tsv"))
        path = alt if os.path.exists(alt) else path
    rank = {}
    if not os.path.exists(path):
        return rank
    with io.open(path, encoding="utf-8") as f:
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
            if not w:
                continue
            try:
                r = int(p[i_r])
            except ValueError:
                continue
            if w not in rank or r < rank[w]:
                rank[w] = r
    return rank


def is_modern(s):
    """候選是否為現代漢語常用詞。

    判定：
      - 單字：必須在常用詞表，且不在 BAD_SINGLE；
      - 雙字及以上：必須在常用詞表，且不在 BAD_WORDS。
    不在表內的放行不了——寧可少一個義項，也不要把「丌」「叟」這種塞給用戶。
    """
    if not s:
        return False
    if s in BAD_WORDS:
        return False
    if len(s) == 1:
        return s in ZH_RANK and s not in BAD_SINGLE
    return s in ZH_RANK


def filter_candidates(cands):
    """進入 AI 精排前先過一遍現代漢語過濾。"""
    keep = [c for c in cands if is_modern(c)]
    return keep if keep else cands[:1]      # 全被濾掉時保底留一個，避免空條目


def load_zf():
    src = io.open(SRC, encoding="utf-8").read()
    m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
    return json.loads(m.group(1))


def norm_fr(s):
    s = re.sub(r"[（(][^）)]*[）)]", " ", (s or "").lower())
    s = re.sub(r"[.,;:!?«»\"'…\[\]]+$", "", s).strip()
    return re.sub(r"\s+", " ", s)


def load_func_keys():
    d = set()
    if os.path.exists(FUNC):
        for line in io.open(FUNC, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                d.add(line.split("\t")[0].strip().lower())
    return d


def build_candidates():
    ZF = load_zf()
    func = load_func_keys()
    cand = collections.defaultdict(set)
    for e in ZF:
        zh, senses = e[1], e[3]
        if not zh or not senses:
            continue
        for raw in senses.split("；"):
            s = norm_fr(raw)
            if not s:
                continue
            s = re.sub(r"^(le|la|les|l'|un|une|des|du|d'|de)\s+", "", s)
            toks = [t for t in re.split(r"[\s,;:]+", s) if t]
            if not (1 <= len(toks) <= MAX_TOKENS):
                continue
            phrase = " ".join(toks)
            if not re.match(r"^[a-zà-ÿœæç' -]+$", phrase):
                continue
            if CJK.match(zh):
                cand[phrase].add(zh)
    # 只精排「多候選 + 非功能詞」的，且候選先過現代漢語過濾
    todo = {}
    for k, v in cand.items():
        if k in func or len(v) < 2:
            continue
        f = filter_candidates(sorted(v))
        if len(f) >= 2:
            todo[k] = f
    return todo


PROMPT_HEAD = """你是法漢詞典編輯。下面每個法語詞後面是從詞庫反演出來的候選中文對應，可能包含錯誤、生僻、詞性不符的項。
請為每個法語詞挑出最貼切的現代漢語對應，按常用程度從高到低排序。

規則：
1. **只排序，不新增**。你返回的每一項必須原樣出現在該詞的候選列表裡。絕對不要發明新詞。
2. 優先選現代漢語口語和書面語都通用的詞，排除文言殘留、生僻字、構詞成分。
   例：chien 的候選有「犬、狗」→ 選「狗」，因為現代漢語說「狗」不說「犬」。
3. 排除與該法語詞義無關的項。
   例：médecin 的候選有「大、医生」→ 只選「医生」。
4. 排除只是構詞成分、不能獨立成詞的單字。
5. 最多返回 4 項。如果候選全都貼切，按常用度排；如果只有 1 項貼切，只返回 1 項。
6. 只輸出 JSON：{"<法語詞>": ["<中文1>", "<中文2>"]}
   不要解釋，不要 markdown 代碼塊。

輸入："""


def build_prompt(batch):
    obj = {w: cands[:12] for w, cands in batch}       # 每詞最多給 12 個候選
    return PROMPT_HEAD + json.dumps(obj, ensure_ascii=False)


def parse_json(text):
    text = str(text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < 0:
        return {}
    try:
        d = json.loads(text[i:j + 1])
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def validate(got, batch):
    """嚴格校驗：返回項必須是候選子集，且必須是現代漢語常用詞。

    這是「AI 不生成譯文」紅線的執行點。模型多給一個詞就說明它在自由發揮，
    這一項直接作廢，不採用。同時擋掉模型把「丌」「叟」這類文言字選進來的情況。
    """
    ok = {}
    for w, cands in batch:
        v = got.get(w)
        if not isinstance(v, list):
            continue
        cset = set(cands)
        kept = []
        for x in v:
            if not isinstance(x, str):
                continue
            x = x.strip()
            if x in cset and x not in kept and is_modern(x):
                kept.append(x)
            if len(kept) >= MAX_GLOSS:
                break
        if kept:
            ok[w] = kept
    return ok


def load_cache():
    c = {}
    if os.path.exists(CACHE):
        for line in io.open(CACHE, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("w") and isinstance(d.get("v"), list) and d["v"]:
                c[d["w"]] = d["v"]
    return c


def main():
    global ZH_RANK
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    assert_endpoint()

    ZH_RANK = load_zh_rank()
    if not ZH_RANK:
        sys.stderr.write("警告：缺中文常用詞表，過濾會失效\n")
    else:
        sys.stderr.write("中文常用詞表 %d 條\n" % len(ZH_RANK))

    todo_all = build_candidates()
    cache = load_cache()
    todo = [(w, c) for w, c in todo_all.items() if w not in cache]
    todo.sort(key=lambda x: len(x[0]))          # 短詞先跑
    if args.limit:
        todo = todo[:args.limit]

    total = len(todo)
    sys.stderr.write("多候選詞 %d，已緩存 %d，待跑 %d\n"
                     % (len(todo_all), len(cache), total))
    if not total:
        return

    batches = [todo[i:i + args.batch] for i in range(0, total, args.batch)]
    q = queue.Queue()
    for b in batches:
        q.put(b)

    lock = threading.Lock()
    done = [0]
    n_ok = [0]
    n_kept = [0]
    t0 = time.time()

    def worker():
        while True:
            try:
                b = q.get_nowait()
            except queue.Empty:
                return
            got = {}
            for attempt in range(3):
                raw = post_chat(build_prompt(b), max_tokens=2000,
                                temperature=0.0, audit_tag="fr2zh_rank")
                if raw:
                    got = parse_json(raw)
                    if got:
                        break
                time.sleep(1.2 * (attempt + 1))

            good = validate(got, b) if got else {}
            with lock:
                if good:
                    with io.open(CACHE, "a", encoding="utf-8") as f:
                        for w, v in good.items():
                            f.write(json.dumps({"w": w, "v": v}, ensure_ascii=False) + "\n")
                    n_ok[0] += len(good)
                n_kept[0] += len(good)
                done[0] += len(b)
                if done[0] % 200 < args.batch:
                    dt = max(1, time.time() - t0)
                    sys.stderr.write("  %d/%d  採用 %d  %.1f 詞/s\n"
                                     % (done[0], total, n_ok[0], done[0] / dt))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    sys.stderr.write("\n完成：%d 詞，耗時 %.0fs，緩存共 %d\n"
                     % (total, time.time() - t0, len(load_cache())))


if __name__ == "__main__":
    main()