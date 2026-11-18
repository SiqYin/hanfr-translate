import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 1) 旧库里的干净例句（按词头）
old = json.load(io.open("data/old_clean.json", encoding="utf-8"))

# 2) 新语料里已翻译的句子（按中文句去重）
translated = {}
for line in io.open("data/cache/examples_clean.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    translated[d["zh_sent"]] = d

# 3) 新语料（全覆盖，质量已修）
corpus = []
for line in io.open("data/corpus_full.jsonl", encoding="utf-8"):
    if line.strip():
        corpus.append(json.loads(line))

# 合并：每个词条取最多 2 条
#   优先用 old（多为汉南语料/首轮翻译，质量最好）
#   不足 2 条时，用 corpus 里已翻译的补
MAX = 2
result = {}
for h, items in old.items():
    result[h] = list(items)[:MAX]

added = 0
for d in corpus:
    h = d["zh"]
    cur = result.get(h, [])
    if len(cur) >= MAX:
        continue
    t = translated.get(d["s"])
    if not t:
        continue
    item = [
        t.get("zh_sent", ""), t.get("fr", ""), t.get("fr_ipa", ""),
        [{"i": L.get("i"), "type": L.get("type"), "phon": L.get("phon", ""),
          "at": L.get("at", "")} for L in (t.get("liaisons") or [])],
        ({"fr": t.get("fr_marked", ""), "ipa": t.get("ipa_marked", "")}
         if (t.get("fr_marked") or t.get("ipa_marked")) else None),
    ]
    result[h] = cur + [item]
    added += 1

with io.open("data/cache/examples_merged.jsonl", "w", encoding="utf-8") as f:
    for h, items in result.items():
        for it in items:
            f.write(json.dumps({
                "zh": h, "zh_sent": it[0], "fr": it[1], "fr_ipa": it[2],
                "liaisons": it[3], "fr_marked": (it[4] or {}).get("fr", ""),
                "ipa_marked": (it[4] or {}).get("ipa", ""),
            }, ensure_ascii=False) + "\n")

n_items = sum(len(v) for v in result.values())
print("合并后：覆盖 %d 词，共 %d 条例句（新增 %d 条来自新语料）"
      % (len(result), n_items, added))
