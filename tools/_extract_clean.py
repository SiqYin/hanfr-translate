import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

z = io.open("app/zhfr_with_examples_backup.js", encoding="utf-8").read()
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))

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


def norm(ex):
    return [] if not ex else (ex if isinstance(ex[0], list) else [ex])


def is_bad(head, sent, fr0):
    if META.search(sent) or not N_PAT.search(sent):
        return False
    if CONCRETE.match(fr0):
        return False
    if len(head) == 1:
        return True
    if re.search(r"(er|ir|re|oir|ment)$", fr0):
        return True
    return False


good = bad = 0
clean = {}
for e in ZF:
    h = e[1]
    fr0 = (e[3] or "").split("；")[0].strip().lower()
    fr0 = re.sub(r"\([^)]*\)", " ", fr0).strip()
    keep = []
    for it in norm(e[6]):
        s = it[0] if it else ""
        if not s:
            continue
        if is_bad(h, s, fr0):
            bad += 1
        else:
            keep.append(it)
            good += 1
    if keep:
        clean[h] = keep

print("提取：干净 %d，剔除 %d，覆盖 %d 词" % (good, bad, len(clean)))
with io.open("data/old_clean.json", "w", encoding="utf-8") as f:
    json.dump(clean, f, ensure_ascii=False)
