import collections
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

z = io.open("app/zhfr.js", encoding="utf-8").read()
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))
sense = {e[1]: (e[3] or "") for e in ZF}

# 名词搭配模板（只适合具体名词）
N_PAT = re.compile(
    r"^(这张|我把|他买了一个新的|这个|请把|我们家的|这批|孩子们在玩|"
    r"你能帮我拿下|他每天都要用到|你能帮我)")

# 判断词是否是「具体名词」：释义以冠词+名词开头
CONCRETE = re.compile(
    r"^(le |la |les |un |une |l')?"
    r"(livre|table|chaise|maison|voiture|ordinateur|téléphone|stylo|sac|"
    r"vêtement|outil|instrument|objet|meuble|appareil|plat|verre|bouteille|"
    r"couteau|fourchette|assiette|clé|clef|portefeuille|parapluie|cahier|"
    r"crayon|chaise|bureau|lit|armoire|réfrigérateur|télévision|radio|"
    r"fichier|disque|mémoire|dossier|stockage|partition|zone|région|"
    r"district|quartier|mois|jour|année|semaine|heure)")

# 语法上通顺、只是信息量低的句子不算病句
# （如「这个声音文件需要定期维护」——语法对，语义稍空）
LOW_INFO = re.compile(r"需要定期维护。$")

bad = []
total = 0
for line in io.open("data/corpus_full.jsonl", encoding="utf-8"):
    if not line.strip():
        continue
    d = json.loads(line)
    h, s = d["zh"], d["s"]
    total += 1
    fr = sense.get(h, "")
    fr0 = fr.split("；")[0].strip().lower()
    fr0 = re.sub(r"\([^)]*\)", " ", fr0).strip()

    if N_PAT.search(s):
        is_concrete = bool(CONCRETE.match(fr0))
        # 元语言句（「这个词写作…」「他在句子里用了…」）语法永远正确，不算病句
        if re.search(r"这个词写作|他在句子里用了|字典里|这个词表示|常用来", s):
            continue
        # 单字、动词、形容词用了名词模板 -> 病句
        if len(h) == 1 and not is_concrete:
            bad.append((h, fr[:18], s, "单字"))
        elif not is_concrete:
            bad.append((h, fr[:18], s, "非具体名词"))

print("语料总句数 %d，病句 %d 条" % (total, len(bad)))
c = collections.Counter(b[3] for b in bad)
for k, v in c.most_common():
    print("  %-10s %d" % (k, v))
print()
for w, fr, s, k in bad[:25]:
    print("  %-6s [%s] %s" % (w, fr, s))
