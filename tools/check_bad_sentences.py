import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "app", "zhfr.js")
z = io.open(SRC, encoding="utf-8").read()
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))


def norm(ex):
    if not ex:
        return []
    if isinstance(ex[0], list):
        return ex
    return [ex]


# 名词模板句式 -> 只适合具体名词
N_PAT = re.compile(
    r"^(这张|我把|他买了一个新的|这个|请把|我们家的|这批|孩子们在玩|"
    r"你能帮我拿下|他每天都要用到)")

# 形容词/动词的常见释义（首义项）
ADJ_FR = re.compile(
    r"^(beau|belle|joli|jolie|grand|petite?|bon|mauvais|important|propre|sale|"
    r"content|heureux|triste|facile|difficile|chaud|froid|rapide|lent|fort|"
    r"faible|riche|pauvre|jeune|vieux|nouveau|long|court|haut|bas|large|"
    r"étroit|clair|sombre|doux|dur|plein|vide|léger|lourd|magnifique|"
    r"splendide|merveilleux|agréable|désagréable|sévère|strict|sincère|noir|"
    r"prospère|efficace|ordonner|appeler|nommer|dire|s'appeler)")
VER_FR = re.compile(r"^(se |s')?[a-zéèêàçA-Z]+(er|ir|re|oir)(；|$)")

# 具体名词：这类词用物量词搭配不算病句（量词不完美但句子成立）
CONCRETE = re.compile(
    r"^(le |la |les |un |une |l')?"
    r"(livre|table|chaise|maison|voiture|ordinateur|téléphone|stylo|sac|"
    r"vêtement|outil|instrument|objet|meuble|appareil|plat|verre|bouteille|"
    r"couteau|fourchette|assiette|clé|clef|portefeuille|parapluie|cahier|"
    r"crayon|bureau|lit|armoire|réfrigérateur|télévision|radio|"
    r"fichier|disque|part|pièce|machine|vélo|moto|train|avion|bateau|"
    r"fruit|légume|fleur|arbre|animal|chien|chat|oiseau|poisson|"
    r"jade|pierre|vase|pot|gorge|corps|organe)")

bad = []
for e in ZF:
    items = norm(e[6])
    for it in items:
        s = it[0] if it else ""
        if not s:
            continue
        fr = (e[3] or "").split("；")[0].strip()
        fr0 = fr.lower()
        fr0 = re.sub(r"\([^)]*\)", " ", fr0).strip()
        # 具体名词（书/桌/椅…）用物量词虽不完美，但不算病句。
        # 只有「非具体名词」套用名词搭配模板才是病句。
        if CONCRETE.match(fr0):
            continue
        # 单字用了名词搭配模板
        if len(e[1]) == 1 and N_PAT.search(s):
            bad.append((e[1], fr[:20], s, "单字用名词模板"))
            continue
        # 形容词/动词用了名词搭配模板
        if (ADJ_FR.match(fr) or VER_FR.match(fr)) and N_PAT.search(s):
            bad.append((e[1], fr[:20], s, "形容词/动词用名词模板"))

print("病句 %d 条" % len(bad))
kinds = collections.Counter(b[3] for b in bad)
for k, v in kinds.most_common():
    print("  %-18s %d" % (k, v))
print()
for w, fr, s, kind in bad[:30]:
    print("  %-6s [%s] %s" % (w, fr, s))
