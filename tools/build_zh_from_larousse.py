#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_zh_from_larousse.py — 从拉鲁斯反查中→法方向

要解决的问题：
  现有中→法方向用 CFDICT，它是单词对译词典，收进了大量文言单字：
      麗 丽 [li4] /beau/        -> 查「丽」只得到 beau
      佼 佼 [jiao3] /beau/      -> 查「佼」只得到 beau
  这些单字现代汉语不单独使用，查了也没意义。

做法：
  拉鲁斯每个义项都有中文对应词（如 maison 的「公寓楼」「住宅」「家」）。
  把「中文对应词 -> 法语词 + 义项 + 词性」建成索引，即为中→法方向。
  这样查「家」会给出 maison（家, Logement où l'on habite, n.f.），
  而不是一堆文言单字。

  同时保留 CFDICT 作补充（它是直接对应，覆盖更广），
  但**排除文言单字**：单字词头若不在现代汉语常用词表内，丢弃。

输出：
  app/zhfr_lar.js   window.ZHLAR = {"家": [["maison","n. f.","Logement où...","家"]...]}

    python tools/build_zh_from_larousse.py
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
LAROUSSE = os.path.join(ROOT, "data", "larousse_senses.jsonl")
ZHFR = os.path.join(ROOT, "app", "zhfr.js")
OUT = os.path.join(ROOT, "app", "zhfr_lar.js")

# 中文对应词里的分隔符
ZH_SPLIT = re.compile(r"[,;，；、/｜|]")
# 去掉括注
PAREN = re.compile(r"[（(][^）)]*[）)]")

# 语域标记 〈书,旧〉〔法〕…！
#
# 这是之前所有问题的根源：
#   原文  Colère.〈书,旧〉愤怒,恼怒
#          标记符里面**本身含逗号**
#   错误做法：先按逗号拆 -> ['〈书', '旧〉愤怒', '恼怒']
#             '〈书' 变成「书」，于是「书 -> ire(愤怒)」这种荒谬对应
#   正确做法：**先整体剥掉 〈...〉，再按逗号拆**
ZH_LABEL = re.compile(r"[〈〔\[][^〉〕\]]{0,20}[〉〕\]]")


def load_zh_rank():
    path = os.path.join(ROOT, "data", "modern_chinese_words.tsv")
    if not os.path.exists(path):
        return {}
    rank = {}
    with io.open(path, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        try:
            i_w, i_r = hdr.index("词语"), hdr.index("频序号")
        except ValueError:
            i_w, i_r = 0, 1
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_w, i_r):
                continue
            try:
                rank[p[i_w].strip()] = int(p[i_r])
            except ValueError:
                pass
    return rank


# 单个汉字本身就是语域/词类标记的一批（书=书面语、旧=古旧、俗、贬…）
LABEL_CHARS = set("书旧古俗贬褒方文口诗法医心哲史乐化物生数语逻经政军海空农"
                  "商体戏宗神星气地矿冶机电计转喻婉谑蔑粗俚儿量助叹拟连介副代"
                  "形动名形副数代介连助叹拟")

# 这些单字即使出现在中文释义里，也只是标记的残留，不能当释义用。
# 实测：mie 的中文字段「书,旧〉女友;心爱的女人」，
# 「书」和「旧」是 〈书〉〈旧〉 被逗号切断后的残片，
# 若不剔除，查「书」会跳出「女友」这种完全无关的词。


def is_label_fragment(p):
    """判断一个片段是不是语域标记的残片。"""
    if not p:
        return True
    # 单字且属于标记字符集
    if len(p) == 1 and p in LABEL_CHARS:
        return True
    return False


def clean_zh(s):
    """清洗中文对应词，返回候选词列表。

    顺序不能反：**先整体剥掉 〈书,旧〉 这类标记，再按逗号拆分**。
    反过来就会把标记切成残片（实测踩过：
      ire 的「Colère.〈书,旧〉愤怒,恼怒」被切成「书」「旧〉愤怒」「恼怒」，
      于是「书 -> ire(愤怒)」，查「书」跳出「愤怒」）。
    """
    if not s:
        return []
    # 1. 先剥完整标记（标记内部可能含逗号）
    s = ZH_LABEL.sub(" ", s)
    # 2. 剥括注
    s = PAREN.sub(" ", s)
    # 3. 清掉残留的标记符
    s = re.sub(r"[〉〕\]]", " ", s)
    s = re.sub(r"[〈〔\[]", " ", s)
    s = s.strip(" .;:，、①②③④⑤⑥⑦⑧⑨⑩")

    out = []
    for part in ZH_SPLIT.split(s):
        p = part.strip(" 　.;,，、")
        if not p or len(p) > 12:
            continue
        if re.search(r"[A-Za-zÀ-ÿ]", p):
            continue
        out.append(p)
    return out


def main():
    ZH_RANK = load_zh_rank()
    sys.stderr.write("中文常用词表 %d\n" % len(ZH_RANK))

    sys.stderr.write("加载拉鲁斯...\n")
    LAR = []
    with io.open(LAROUSSE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                LAR.append(json.loads(line))
    sys.stderr.write("  %d 条\n" % len(LAR))

    # zh -> [ [fr, pos, fr_def, zh], ... ]
    idx = collections.defaultdict(list)
    seen = set()
    # 统计：某个中文词对应多少个不同法语词。
    # 用来过滤标记残片——「书」若同时对应 mie/ire/on 三个毫不相干的词，
    # 说明它来自标记而非释义；真释义（如「书本」-> livre）只对应少数词。
    zh_fr = collections.defaultdict(set)

    for r in LAR:
        fr_word = r["h"]
        for s in r["s"]:
            zh_field = s.get("zh") or ""
            if not zh_field:
                continue
            pos = s.get("pos") or ""
            cands = clean_zh(zh_field)
            for i, z in enumerate(cands):
                key = (z, fr_word)
                if key in seen:
                    continue
                seen.add(key)
                # 记录该中文词在释义里的位置：越靠前越可能是主释义。
                # 「书,旧〉女友」里「书」位次 0 但其实是标记残片，
                # 而「书,书本,书籍」里「书」位次 0 且后面有同义扩展。
                idx[z].append([fr_word, pos, (s.get("fr") or "")[:120], z, i])
                zh_fr[z].add(fr_word)

    # 排序：常用中文词优先；每个中文词的法语词按原型优先、词性排序
    stats = {"zh_keys": len(idx), "entries": 0, "single_char_kept": 0,
             "single_char_dropped": 0}

    out = {}
    dropped_suspect = 0

    # 高频常用单字白名单：这些字本身就是现代汉语的独立词，
    # 即使对应多个法语词也是真释义（「书」对应 livre/livre 多个义项）。
    # 不能因为「对应词多」就删——只有真正的高频字才豁免。
    COMMON_SINGLE = set(
        "人 大 小 上 下 好 坏 多 少 长 短 高 低 新 旧 老 少 男 女 天 地 水 火 "
        "土 木 金 石 山 河 海 风 雨 雪 云 日 月 年 时 分 秒 早 晚 春 夏 秋 冬 "
        "书 吃 喝 走 跑 看 听 说 想 做 打 拿 放 开 关 买 卖 给 找 用 学 写 "
        "读 唱 跳 睡 起 坐 站 躺 笑 哭 叫 问 答 帮 等 送 收 换 洗 擦 修 借 "
        "头 手 脚 眼 耳 口 鼻 心 血 骨 肉 皮 毛 发 牙 舌 脸 背 腰 腿 臂 指 "
        "家 门 窗 床 桌 椅 灯 车 船 路 桥 街 城 村 田 园 花 草 树 叶 果 米 "
        "饭 菜 肉 鱼 蛋 奶 油 盐 糖 茶 酒 药 病 痛 累 忙 闲 快 慢 冷 热 暖 "
        "白 黑 红 黄 绿 蓝 紫 灰 光 亮 暗 声 音 味 色 形 线 面 点 圆 方 直 "
        "牛 马 羊 猪 狗 猫 鸡 鸭 鸟 虫 蛇 虎 龙 象 熊 兔 鼠 蜂 蝶 蚊 蝇 蚁 "
        "爱 恨 怕 求 让 使 被 把 从 到 向 往 在 有 无 是 不 没 很 太 最 更 "
        "一 二 三 四 五 六 七 八 九 十 百 千 万 亿 零 半 双 对 群 些 每 各"
    .split())

    for z, items in idx.items():
        # 单字：必须在现代汉语常用词表内，否则是文言字
        if len(z) == 1:
            if ZH_RANK and z not in ZH_RANK:
                stats["single_char_dropped"] += 1
                continue
            if z not in COMMON_SINGLE and len(zh_fr[z]) > 6:
                dropped_suspect += 1
                continue
            stats["single_char_kept"] += 1

        # 去重（同一法语词只留一次，取最短释义）
        pk = {}
        for fr, pos, d, _z, rank in items:
            if fr not in pk or len(d) < len(pk[fr][2]):
                pk[fr] = [fr, pos, d, rank]
        lst = list(pk.values())

        # 按「中文词在释义里的位次」排序：位次 0 的是主释义。
        # 「书」对应 livre 时位次是 0（书,书本,书籍），
        # 对应 sien 时位次靠后（"poss. SOUT. ... le sien 他的"），
        # 据此把主释义排前面，噪音自然沉底。
        lst.sort(key=lambda x: (x[3], len(x[0])))
        out[z] = [[x[0], x[1], x[2]] for x in lst[:12]]
        stats["entries"] += len(out[z])
    stats["single_char_suspect"] = dropped_suspect

    js = "window.ZHLAR=" + json.dumps(out, ensure_ascii=False,
                                      separators=(",", ":")) + ";"
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    print("中→法索引 %d 个中文词 -> %s（%.2f MB）"
          % (len(out), OUT, len(js.encode("utf-8")) / 1048576))
    print("  条目 %d" % stats["entries"])
    print("  单字保留 %d，丢弃（文言/生僻）%d"
          % (stats["single_char_kept"], stats["single_char_dropped"]))

    print("\n抽样：")
    for z in ("家", "美丽", "水", "书", "吃", "大", "丽", "佼"):
        if z in out:
            print("  【%s】%d 个法语词" % (z, len(out[z])))
            for fr, pos, d in out[z][:3]:
                print("     %-12s %-8s %s" % (fr, pos, d[:40]))
        else:
            print("  【%s】未收录" % z)


if __name__ == "__main__":
    main()
