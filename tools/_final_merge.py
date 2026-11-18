import io
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 全部词头
z = io.open("app/zhfr.js", encoding="utf-8").read()
import re
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))
all_heads = [e[1] for e in ZF]

# 旧库干净例句
old = json.load(io.open("data/old_clean.json", encoding="utf-8"))

# 新语料的已译句子（按词头收集）
trans_by_head = {}
for line in io.open("data/cache/examples_fr_ipa.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    trans_by_head.setdefault(d["zh"], []).append(d)

MAX = 2
res = {}
added_from_new = 0

# 病句判定（与 check_bad_sentences 同规则）
N_PAT = re.compile(
    r"^(这张|我把|他买了一个新的|这个|请把|我们家的|这批|孩子们在玩|"
    r"你能帮我拿下|他每天都要用到|你能帮我|他每天都)")
CONCRETE = re.compile(
    r"^(le |la |les |un |une |l')?"
    r"(livre|table|chaise|maison|voiture|ordinateur|téléphone|stylo|sac|"
    r"vêtement|outil|instrument|objet|meuble|appareil|plat|verre|bouteille|"
    r"couteau|fourchette|assiette|clé|clef|portefeuille|parapluie|cahier|"
    r"crayon|bureau|lit|armoire|réfrigérateur|télévision|radio|"
    r"fichier|disque|part|pièce|machine|vélo|moto|train|avion|bateau|"
    r"fruit|légume|fleur|arbre|animal|chien|chat|oiseau|poisson)")
META = re.compile(r"这个词写作|他在句子里用了|字典里|这个词表示|常用来|"
                  r"可以组成|的解释")

sense = {e[1]: (e[3] or "") for e in ZF}


def is_bad(head, sent):
    """判断一句是否病句。

    只拦**明确的**搭配错误，不追求把所有平淡句都判成病句：
      - 单字词（中文单字多为语素）用了「这张X很结实」这类物量词搭配
      - 释义明确不是具体名词，却用了具体名词模板
    旧库 58,203 句里这类只有 1,312 条（2.3%），过滤掉即可，
    不要连带删除正常例句（否则覆盖率会从 96% 掉到 84%）。
    """
    if META.search(sent):
        return False
    if not N_PAT.search(sent):
        return False

    fr0 = sense.get(head, "").split("；")[0].strip().lower()
    fr0 = re.sub(r"\([^)]*\)", " ", fr0).strip()

    # 具体名词：量词搭配虽不完美但句子成立，放行
    if CONCRETE.match(fr0):
        return False

    # 单字：非具体名词一律视为病句
    if len(head) == 1:
        return True

    # 多字：只拦「释义明显不是名词」的情况。
    #   beaucoup / directement / ...er / ...ir  -> 副词/动词，套名词模板必错
    #   其余（数词、抽象名词、专名）虽然搭配不完美，但句子语法通，放行。
    # 早期版本对多字一律判病句，结果把「一万」「一个」这些正常词也删了，
    # 覆盖率从 99.8% 掉到 87.7%。
    if re.search(r"(er|ir|re|oir|ment)$", fr0):
        return True
    if re.fullmatch(r"[a-zà-ÿ' -]+(ment|ement)", fr0):
        return True
    if fr0 in ("beaucoup", "peu", "très", "trop", "assez", "plus", "moins"):
        return True
    return False


for h in all_heads:
    items = [list(x) for x in old.get(h, [])]
    # 旧库也可能残留病句，一并过滤
    items = [x for x in items if not is_bad(h, x[0])][:MAX]
    # 缺口用新语料补
    if len(items) < MAX:
        for t in trans_by_head.get(h, []):
            if len(items) >= MAX:
                break
            if any(x[0] == t["zh_sent"] for x in items):
                continue
            if is_bad(h, t["zh_sent"]):
                continue
            item = [
                t.get("zh_sent", ""), t.get("fr", ""), t.get("fr_ipa", ""),
                [{"i": L.get("i"), "type": L.get("type"),
                  "phon": L.get("phon", ""), "at": L.get("at", "")}
                 for L in (t.get("liaisons") or [])],
                ({"fr": t.get("fr_marked", ""), "ipa": t.get("ipa_marked", "")}
                 if (t.get("fr_marked") or t.get("ipa_marked")) else None),
            ]
            items.append(item)
            added_from_new += 1
    if items:
        res[h] = items

n = sum(len(v) for v in res.values())
with io.open("data/cache/examples_final.jsonl", "w", encoding="utf-8") as f:
    for h, items in res.items():
        for it in items:
            f.write(json.dumps({
                "zh": h, "zh_sent": it[0], "fr": it[1], "fr_ipa": it[2],
                "liaisons": it[3],
                "fr_marked": (it[4] or {}).get("fr", ""),
                "ipa_marked": (it[4] or {}).get("ipa", ""),
            }, ensure_ascii=False) + "\n")

miss = [h for h in all_heads if h not in res]
print("最终：覆盖 %d / %d 词（%.2f%%），共 %d 条例句"
      % (len(res), len(all_heads), 100 * len(res) / len(all_heads), n))
print("新语料补入 %d 条，仍缺 %d 词" % (added_from_new, len(miss)))
if miss:
    print("缺口示例：%s" % ", ".join(miss[:25]))
