import collections
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"app\zhfr.js"
z = io.open(SRC, encoding="utf-8").read()
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))


def norm(ex):
    if not ex:
        return []
    if isinstance(ex[0], list):
        return ex
    return [ex]


# 名词模板的标志句
N_TELLS = [
    "这张{w}很结实", "我把{w}放在桌子上", "他买了一个新的{w}",
    "这个{w}多少钱", "请把{w}递给我", "{w}在房间的角落",
    "她喜欢这个{w}", "我们家的{w}坏了", "这批{w}的质量",
    "他每天都要用到{w}", "孩子们在玩那个{w}", "请把{w}擦干净",
    "{w}放在哪儿了", "你能帮我拿下那个{w}",
]

# 形容词的法语标志（释义以这些开头，说明词条是形容词）
ADJ_FR = re.compile(
    r"^(beau|belle|joli|jolie|grand|petit|bon|mauvais|important|"
    r"propre|sale|content|heureux|triste|facile|difficile|"
    r"chaud|froid|rapide|lent|fort|faible|riche|pauvre|"
    r"jeune|vieux|nouveau|long|court|haut|bas|large|étroit|"
    r"clair|sombre|doux|dur|plein|vide|léger|lourd|"
    r"magnifique|splendide|merveilleux|agréable|désagréable)")

# 动词的法语标志
VER_FR = re.compile(r"^(se |s')?[a-zéèêàç]+(er|ir|re|oir)$")

bad = []
for e in ZF:
    items = norm(e[6])
    if len(items) < 2:
        continue
    # 检查第二条
    s2 = items[1][0] if items[1] else ""
    fr = (e[3] or "").upper()
    fr_raw = (e[3] or "")
    for tpl in N_TELLS:
        pat = tpl.replace("{w}", e[1])
        if pat in s2:
            # 该词若是形容词/动词，用名词模板就是病句
            if ADJ_FR.match(fr_raw) or VER_FR.match(fr_raw.split("；")[0]):
                bad.append((e[1], fr_raw[:24], s2))
            break

print("可疑病句 %d 条" % len(bad))
for w, fr, s in bad[:40]:
    print("  %-6s [%s] %s" % (w, fr, s))
