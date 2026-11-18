#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_full_corpus.py — 全覆盖例句语料生成器（v2，按词义分模板）

v1 的问题：只按「词形」分类（字母词/数字词/生僻字/普通词），
同一类共用一套模板，于是出现了：
    这个K粉需要重新格式化。   ← K粉 是毒品，不是硬盘
    请检查K粉的剩余空间。
    他住在10月。              ← 10月 是月份，不是街道
    沿着10月一直走就到了。

这是编造，不是数据。用户要求全覆盖，但**不能靠病句凑数**。

v2 做法：先按**法语释义**判断词的语义类别，再选对应模板。
    C盘 -> 磁盘/存储
    K粉 -> 毒品/违禁
    10月 -> 月份/时间
    42街 -> 街道/地点
    T裇  -> 衣物
    㑇  -> 生僻字/古籍

法语释义本来就在词库里（e[3]），用它做分类依据是可靠的。

    python tools/build_full_corpus.py
"""
import collections
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "app", "zhfr.js")
OUT = os.path.join(ROOT, "data", "corpus_full.jsonl")

rows = []
seen = set()
covered = collections.Counter()
stat = collections.Counter()


def add(head, sent, kind):
    sent = (sent or "").strip()
    if not sent or head not in sent:
        return False
    if sent in seen:
        return False
    if len(sent) < 5 or len(sent) > 60:
        return False
    seen.add(sent)
    rows.append({"zh": head, "s": sent, "src": kind})
    covered[head] += 1
    stat[kind] += 1
    return True


# ---------------- 语义分类：看法语释义 ----------------
SEM_RULES = [
    # (语义类别, 释义关键词正则)
    # 顺序重要：更具体的规则放前面。
    # 注意：只看**首义项**——「跑」的释义里括注了 (pour un animal)，
    # 全文匹配会把它误判成动物。
    ("drug",    r"kétamine|drogue|stupéfiant|narcotique|héroïne|cocaïne|opium"),
    ("org",     r"ministère|comité|bureau|agence|organisation|fédération|"
                r"association|société|entreprise|compagnie|institut|"
                r"université|école|hôpital|banque"),
    ("disk",    r"\bdisque|^disque|lecteur de disque|stockage|"
                r"^(un |le )?fichier|mémoire morte|dossier"),
    ("cloth",   r"t-shirt|vêtement|habit|robe|pantalon|caleçon"),
    ("lingerie", r"sous-vêtement|serviette hygiénique|string|soutien-gorge|"
                 r"décolleté|culotte|lingerie"),
    ("person",  r"influenceur|blogueur|personnalité|célébrité|vedette"),
    ("web",     r"internet|réseau|web|blog|photoshop|image|réseaux sociaux|"
                r"retouche|photo"),
    ("month",   r"^(janvier|février|mars|avril|mai|juin|juillet|août|"
                r"septembre|octobre|novembre|décembre)"),
    ("street",  r"rue|avenue|boulevard"),
    ("place",   r"quartier|secteur|district|arrondissement|zone|région|"
                r"comité de quartier|épicerie de quartier"),
    ("region",  r"région|zone|aire|bassin|vallée|plateau|plaine|désert"),
    ("time",    r"jour|semaine|mois|année|heure|minute|période|délai|"
                r"journée"),
    ("number",  r"^\d|nombre|chiffre|numéro|version|modèle|type|série|"
                r"position|section"),
    ("plant",   r"plante|herbe|fleur|arbre|végétal|ortie|orchidée"),
    ("animal",  r"animal|insecte|oiseau|poisson|coccinelle|tigre|bête"),
    ("mineral", r"jade|pierre|minéral|métal|cristal"),
    ("chem",    r"element|chimique|meitnérium|chrysène|isotope|molécule"),
    ("body",    r"gorge|corps|organe|tête|main|pied|ventre|dos"),
    ("object",  r"^vase|^pot|récipient|^outil|^ustensile|^objet|^instrument"),
    # 注意：这里**不放 adj 规则**。
    # 形容词由 is_adj_by_fr() 单独判断，因为它要区分「常用形容词」与
    # 「生僻形容词」——前者可以用真实搭配，后者只能用语元说明句。
    # 若在这里加 adj，sem_of 会先命中，把这个区分抹掉。
]

SEM_TPL = {
    "adj": [
        "「{w}」是个形容词。",
        "这个词可以用来形容事物「{w}」。",
        "「{w}」常用来描写状态。",
        "字典里把「{w}」标为形容词。",
        "「{w}」可以修饰名词。",
        "「{w}」在句子里作定语或表语。",
        "他说这地方很{w}。",
        "「{w}」有程度上的差别。",
    ],
    "org": [
        "{w}负责这项工作的统筹。", "{w}今年发布了新的规定。",
        "{w}的办公地点在城东。", "他曾在{w}工作过三年。",
        "{w}下设多个部门。", "{w}对这件事作出了回应。",
    ],
    "disk": [
        "{w}的容量已经不够了。", "他检查了{w}的剩余空间。",
        "{w}里存着大量资料。", "系统提示{w}无法访问。",
        "这个{w}需要定期维护。", "{w}的速度比原来快很多。",
    ],
    "drug": [
        "警方在机场查获了一批{w}。", "{w}对身体有严重危害。",
        "他因为吸食{w}被拘留。", "{w}属于国家管制的违禁品。",
        "医生提醒青少年远离{w}。", "这种{w}在黑市上价格很高。",
    ],
    "cloth": [
        "她买了一件{w}。", "这件{w}的料子很舒服。", "他穿着{w}就去上班了。",
        "这条{w}是今年流行的款式。", "{w}在夏天穿最合适。", "他把{w}洗了晾在阳台上。",
    ],
    "lingerie": [
        "她买了一条{w}。", "这家店专卖{w}。", "{w}放在内衣专柜。",
        "她挑了一件{w}。", "这种{w}的尺码偏小。", "她在网上订了几条{w}。",
    ],
    "month": [
        "{w}的天气开始转凉。", "会议定在{w}。", "{w}的时候我们会放假。",
        "他去年的{w}来过一次。", "{w}是旅游旺季。", "这份报告要在{w}之前交。",
    ],
    "street": [
        "{w}这一带很热闹。", "他住在{w}。", "沿着{w}一直走就到了。",
        "{w}的商店都关门了。", "我在{w}的路口等他。", "{w}上有一家老书店。",
    ],
    "place": [
        "{w}位于城市南边。", "{w}的面积不大。", "{w}的人口这几年增长很快。",
        "他工作的地方属于{w}。", "{w}的规划已经完成。", "这个{w}靠近河边。",
    ],
    "region": [
        "{w}位于中国南方。", "{w}的气候比较湿润。", "{w}的经济发展很快。",
        "他出生在{w}。", "{w}以农业为主。", "{w}的面积占全省的三分之一。",
    ],
    "time": [
        "{w}之后再联系吧。", "他花了很长时间才熬过{w}。", "我们在{w}见面。",
        "{w}里他一直在出差。", "{w}是全年最忙的时候。", "他{w}几乎没休息过。",
    ],
    "web": [
        "他在{w}上很活跃。", "这篇帖子在{w}上被转发了上万次。",
        "她用{w}把照片修得很漂亮。", "他靠{w}赚了不少钱。",
        "这条消息在{w}上引起了热议。", "{w}之后照片完全看不出痕迹。",
    ],
    "person": [
        "他是一位知名的{w}。", "这位{w}的粉丝超过一百万。",
        "{w}在社交媒体上很活跃。", "这家公司请了{w}来做推广。",
        "那位{w}因为一条视频走红。", "{w}的言论引起了争议。",
    ],
    "number": [
        "他开的是{w}型的车。", "这种{w}的装备已经淘汰了。",
        "{w}的款式很少见。", "他买了一块{w}的手表。",
        "这是{w}版本的软件。", "{w}的规格和旧款不同。",
    ],
    "plant": [
        "{w}在路边随处可见。", "这种{w}可以入药。", "{w}的叶子是椭圆形的。",
        "他在院子里种了一些{w}。", "{w}在春天开花。", "这种{w}喜欢阴湿的环境。",
    ],
    "animal": [
        "{w}主要生活在山区。", "他在野外看到一只{w}。", "{w}以昆虫为食。",
        "这种{w}的数量正在减少。", "{w}的皮毛很厚。", "孩子们在动物园看到了{w}。",
    ],
    "mineral": [
        "这块{w}质地温润。", "{w}是珍贵的雕刻材料。", "他在集市上买了一块{w}。",
        "{w}的颜色很深。", "这种{w}产自新疆。", "{w}被做成了一枚印章。",
    ],
    "chem": [
        "{w}是一种化学元素。", "实验室里存放着{w}。", "{w}在自然界中含量极少。",
        "科学家首次合成了{w}。", "{w}的半衰期很短。", "{w}属于超重元素。",
    ],
    "body": [
        "他的{w}有些发炎。", "医生检查了他的{w}。", "{w}不舒服要多喝水。",
        "她捂着{w}说疼。", "{w}的症状持续了三天。", "感冒常引起{w}不适。",
    ],
    "object": [
        "这个{w}是青铜做的。", "考古队挖出了一个{w}。", "{w}表面有精美的纹饰。",
        "他把{w}摆在案头。", "这件{w}是汉代的。", "{w}已经残缺不全。",
    ],
}

# 生僻字：用释名式，这类字现代汉语本就不单独成词
TPL_RARE = [
    "{w}是古代的一个字。", "{w}这个字现在已经很少用了。",
    "字典里{w}的释义是古代的用法。", "{w}属于生僻字，多见于古籍。",
    "这个{w}字在《说文解字》里有记载。", "他查了半天才找到{w}这个字。",
    "{w}在现代汉语中已经不再使用。", "手写{w}需要记住笔顺。",
    "{w}的字形比较复杂。", "古籍中常见{w}这个字。",
]

# 单字：一律用字词说明式。这类句子语义中立，不会因为词性判断失误而错配。
# 不用「这个字很好写」（对「上」「书」不自然），改用字典语境。
TPL_SINGLE = [
    "「{w}」这个字在汉语里很常用。",
    "字典里对「{w}」的解释有好几条。",
    "「{w}」可以组成很多词语。",
    "他查字典确认「{w}」的读音。",
    "「{w}」在古文和现代汉语里都在用。",
    "老师让学生用「{w}」组词。",
    "这个「{w}」字笔画不多。",
    "「{w}」在不同语境里意思不一样。",
    "他一时想不起「{w}」怎么写。",
    "「{w}」是多音字，要看上下文。",
]

# 普通词
TPL_N = [
    "这张{w}很结实。", "我把{w}放在桌子上了。", "他买了一个新的{w}。",
    "这个{w}多少钱？", "请把{w}递给我。", "{w}在房间的角落里。",
    "她喜欢这个{w}。", "我们家的{w}坏了，需要修理。",
    "他把{w}送给了朋友。", "这个{w}看起来很不错。",
    "你能帮我拿下那个{w}吗？", "{w}放在哪儿了？",
    "这批{w}的质量很好。", "他每天都要用到{w}。",
    "我昨天在商店看到一个很漂亮的{w}。", "这个{w}比那个贵一点。",
    "孩子们在玩那个{w}。", "请把{w}擦干净。",
    "他把{w}从柜子里拿了出来。", "这个{w}已经用了很多年了。",
]
# 动词：用的是「不指定主语意图」的中性句式。
# 「他们决定上吊」这种句子虽然语法通，但语义荒谬；
# 换成「这个词表示…」或「…这个词常用来表达…」的元语言句式更安全。
# 形容词：分两档。
#   ADJ_SAFE  —— 语义明确、搭配不会错的常用形容词，用真实描写句
#   其余        —— 用元语言说明句（避免「这件衣服看起来很一头」）
TPL_V = [
    "「{w}」这个词表示一个动作。",
    "「{w}」常用来表达某种行为。",
    "他在句子里用了「{w}」。",
    "「{w}」是个动词。",
    "字典里把「{w}」标为动词。",
    "「{w}」可以带宾语。",
    "「{w}」在不同的句子里意思略有不同。",
    "这个词写作「{w}」。",
    "「{w}」的用法要看上下文。",
]

# 形容词分三档：
#   情绪/心理类 —— 主语必须是人
#   其他常用    —— 可以形容事物
#   生僻/不明   —— 用语元说明句
TPL_ADJ_EMOTION = [
    "他今天显得很{w}。", "她看起来有点{w}。",
    "听到这个消息，他很{w}。", "孩子们玩得很{w}。",
    "他最近心情很{w}。", "她笑得那么{w}。",
]
ADJ_EMOTION_SET = set("""
高兴 快乐 幸福 难过 悲伤 生气 着急 紧张 兴奋 激动 失望 满意
开心 愉快 忧愁 烦恼 焦虑 害怕 惊讶 感动 骄傲 惭愧 内疚 委屈
""".split())

TPL_ADJ_SAFE = [
    "这里的景色很{w}。", "他今天的心情很{w}。",
    "这件衣服看起来很{w}。", "那家店的布置很{w}。",
    "她的回答很{w}。", "这个想法听起来很{w}。",
    "雨后的空气很{w}。", "他说话的语气很{w}。",
]
ADJ_SAFE_SET = set("""
美丽 漂亮 好看 高兴 快乐 幸福 难过 悲伤 生气 着急 紧张 轻松
干净 整齐 脏 乱 安静 吵闹 热闹 冷清 明亮 昏暗 宽敞 狭窄
新鲜 陈旧 好吃 难吃 香甜 苦涩 温暖 寒冷 凉爽 闷热 干燥 潮湿
简单 复杂 容易 困难 重要 关键 危险 安全 健康 强壮 虚弱 疲劳
聪明 愚蠢 认真 马虎 仔细 粗心 诚实 狡猾 善良 凶狠 温柔 粗暴
大 小 多 少 长 短 高 低 快 慢 新 旧 好 坏 美 丑 贵 便宜
""".split())

TPL_ADJ_META = [
    "「{w}」是个形容词。",
    "「{w}」常用来描写状态。",
    "字典里把「{w}」标为形容词。",
    "「{w}」可以修饰名词。",
    "「{w}」在句子里作定语或表语。",
    "「{w}」有程度上的差别。",
]
TPL_A = [
    "今天的天气很{w}。", "这件衣服看起来很{w}。",
    "他家的院子特别{w}。", "这个想法很{w}。",
    "她的房间收拾得很{w}。", "这条路很{w}。",
    "那家餐厅的菜很{w}。", "他说话的语气很{w}。",
    "这个地方比以前{w}多了。", "孩子画得又{w}又生动。",
    "这个方案听起来很{w}。", "雨后的空气特别{w}。",
    "他的回答很{w}。", "这朵花开得真{w}。",
    "今天的天空特别{w}。", "她的字写得很{w}。",
    "这件家具看着很{w}。", "他今天心情很{w}。",
    "这部电影很{w}。", "山上的风景非常{w}。",
]

VERB_END = re.compile(
    r"(做|走|跑|吃|喝|看|说|想|来|去|买|卖|学|写|读|听|睡|起|开|关|放|拿|给|"
    r"找|问|答|帮|等|用|玩|唱|跳|洗|擦|修|打|叫|称|拉|吸|念|背|站|坐|躺)$")
ADJ_END = re.compile(r"(的|地|得)$")

EXT_BLOCKS = [(0x3400, 0x4DBF), (0x20000, 0x2A6DF), (0x2A700, 0x2B73F),
              (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF), (0x2CEB0, 0x2EBEF),
              (0x30000, 0x3134F), (0xF900, 0xFAFF)]


def is_rare(h):
    return any(0x3400 <= ord(c) and not (0x4e00 <= ord(c) <= 0x9fff)
               for c in h) or any(EXT_BLOCKS[0][0] <= ord(c) <= EXT_BLOCKS[0][1]
                                  for c in h)


def sem_of(sense):
    """只看首义项判断语义类别。

    全文匹配会误判——「跑」的释义写成
        courir；s'enfuir；...；gratter le sol (pour un animal)
    含 animal，整条匹配就把它归成动物了。取首义项即可避免。
    """
    s = (sense or "").split("；")[0].strip().lower()
    for name, pat in SEM_RULES:
        if re.search(pat, s):
            return name
    return ""


def is_adj_by_fr(sense):
    """是否形容词。先去掉括注再匹配，避免 (arch.) 之类干扰。"""
    raw = (sense or "").split("；")[0].strip().lower()
    # 依次尝试每个义项的首词，直到命中
    for part in (sense or "").split("；")[:3]:
        s = re.sub(r"\([^)]*\)", " ", part).strip().lower()
        s = re.sub(r"^(le |la |les |un |une )", "", s).strip()
        if re.match(
                r"^(beau|belle|joli|jolie|grand|petite?|bon|mauvais|important|"
                r"propre|sale|content|heureux|triste|facile|difficile|chaud|"
                r"froid|rapide|lent|fort|faible|riche|pauvre|jeune|vieux|"
                r"nouveau|long|court|haut|bas|large|étroit|clair|sombre|doux|"
                r"dur|plein|vide|léger|lourd|magnifique|splendide|merveilleux|"
                r"agréable|désagréable|sévère|strict|sincère|noir|prospère|"
                r"efficace|ordinaire|heureux)\b", s):
            return True
    return False


def is_verb_by_fr(sense):
    """用法语首义项判断是不是动词。

    中文词尾判断不可靠（「上传」「上升」不是「传」「升」结尾的构词规律），
    但法语释义很明确：动词以 -er/-ir/-re/-oir 结尾，且不带冠词。
    """
    s = (sense or "").split("；")[0].strip().lower()
    if not s:
        return False
    # 去掉 se/s' 前缀与括注
    s = re.sub(r"\([^)]*\)", " ", s).strip()
    s = re.sub(r"^(se |s')", "", s)
    # 单动词形态
    if re.fullmatch(r"[a-zà-ÿœæ'-]+(er|ir|re|oir)", s):
        return True
    return False


# （旧版 is_adj_by_fr 已移除，见上方按义项逐个匹配的版本）


def tpls_for(head, sense):
    """按语义选模板。

    单字特殊处理：中文单字多为**语素**而非独立词，
    「这张书很结实」「这个美丽多少钱」都不通。

    多字词也要判断词性：法语释义以 -er/-ir/-re/-oir 结尾的就是动词，
    用名词模板会得到「他买了一个新的上传」这种病句（实测 8,557 条）。
    """
    is_single = len(head) == 1
    sem = sem_of(sense)

    # 单字能用搭配模板的类别
    SINGLE_OK = {"object", "animal", "plant", "body", "mineral", "chem",
                 "drug", "disk", "cloth", "lingerie", "street", "place",
                 "month", "time", "number", "person", "web"}

    if sem and (not is_single or sem in SINGLE_OK):
        return SEM_TPL[sem], sem

    if is_rare(head):
        return TPL_RARE, "rare"

    if is_single:
        return TPL_SINGLE, "single"

    # 多字：按法语释义判词性
    if is_adj_by_fr(sense):
        if head in ADJ_EMOTION_SET:
            return TPL_ADJ_EMOTION, "adjemo"
        if head in ADJ_SAFE_SET:
            return TPL_ADJ_SAFE, "adj"
        return TPL_ADJ_META, "adjmeta"
    if is_verb_by_fr(sense):
        return TPL_V, "verb"
    if ADJ_END.search(head) and head in ADJ_EMOTION_SET:
        return TPL_ADJ_EMOTION, "adjemo"
    if ADJ_END.search(head) and head in ADJ_SAFE_SET:
        return TPL_ADJ_SAFE, "adj"
    if ADJ_END.search(head):
        return TPL_ADJ_META, "adjmeta"
    if VERB_END.search(head):
        return TPL_V, "verb"

    # 兜底：判不出词性、且释义不像具体名词的，用元语言句。
    # 「一头」释义是 directement（副词，以 -ment 结尾），
    # 若把 -ment 当名词后缀就会误判成「他买了一个新的一头」。
    fr0 = (sense or "").split("；")[0].strip().lower()
    fr0 = re.sub(r"\([^)]*\)", " ", fr0).strip()
    # 明显是副词/介词/连词/代词 -> 不是名词
    if re.match(r"^[a-zà-ÿ]+(ment|emment)$", fr0) or \
       fr0 in ("et", "ou", "mais", "donc", "or", "ni", "car") or \
       re.match(r"^(à|de|en|par|pour|sans|sous|sur|avec|chez|dans|entre|vers)\b", fr0):
        return TPL_V, "meta"
    looks_mass_noun = bool(
        re.match(r"^(le |la |les |un |une |l')?(livre|table|chaise|maison|"
                 r"voiture|ordinateur|téléphone|stylo|sac|vêtement|outil|"
                 r"instrument|objet|meuble|appareil)", fr0))
    if looks_mass_noun:
        return TPL_N, "noun"
    return TPL_V, "meta"


def main():
    src = io.open(SRC, encoding="utf-8").read()
    ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S).group(1))
    sys.stderr.write("词条 %d\n" % len(ZF))

    MAX_PER = 2
    for rnd in range(MAX_PER):
        added = 0
        for e in ZF:
            h = e[1]
            if covered[h] >= rnd + 1:
                continue
            tpls, kind = tpls_for(h, e[3])
            t = tpls[(rnd + len(h)) % len(tpls)]
            if add(h, t.replace("{w}", h), kind):
                added += 1
        sys.stderr.write("  第 %d 轮 +%d，累计 %d 句 / 覆盖 %d 词\n"
                         % (rnd + 1, added, len(rows), len(covered)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n总句数 %d -> %s" % (len(rows), OUT))
    for k, v in stat.most_common():
        print("  %-10s %7d" % (k, v))
    miss = [e[1] for e in ZF if covered[e[1]] == 0]
    print("未覆盖词头 %d" % len(miss))
    if miss:
        print("  %s" % ", ".join(miss[:20]))


if __name__ == "__main__":
    main()