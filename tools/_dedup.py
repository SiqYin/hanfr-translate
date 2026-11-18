import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

p = "tools/build_full_corpus.py"
src = io.open(p, encoding="utf-8").read()

# 删掉第二个（旧版）is_adj_by_fr 定义
old_block = '''def is_adj_by_fr(sense):
    s = (sense or "").split("；")[0].strip().lower()
    s = re.sub(r"\\([^)]*\\)", " ", s).strip()
    return bool(re.fullmatch(
        r"(beau|belle|joli|jolie|grand|petite?|bon|mauvais|important|propre|"
        r"sale|content|heureux|triste|facile|difficile|chaud|froid|rapide|lent|"
        r"fort|faible|riche|pauvre|jeune|vieux|nouveau|long|court|haut|bas|"
        r"large|étroit|clair|sombre|doux|dur|plein|vide|léger|lourd|"
        r"magnifique|splendide|merveilleux|agréable|désagréable|sévère|strict|"
        r"sincère|noir|prospère|efficace|ordinaire|directement)", s))'''

if old_block in src:
    src = src.replace(old_block, "# （旧版 is_adj_by_fr 已移除，见上方按义项逐个匹配的版本）", 1)
    print("已删除重复定义")
else:
    # 尝试用正则定位
    m = list(re.finditer(r"\ndef is_adj_by_fr\(sense\):\n(?:    .*\n|\n)*?(?=\ndef |\nTPL|\n# )", src))
    print("正则命中 %d 处" % len(m))
    if len(m) >= 2:
        s, e = m[1].span()
        src = src[:s] + "\n# （旧版 is_adj_by_fr 已移除）\n" + src[e:]
        print("已用正则删除第二处")

io.open(p, "w", encoding="utf-8").write(src)
