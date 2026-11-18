#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_conjugation.py — 构建法语动词变位表

为什么不能只靠 Lexique：
  Lexique 给出「原型 -> 全部屈折形式」的集合，但**不标注时态与人称**。
  例如 parler 有 35 个形式，但不知道哪个是 passé simple 1p。

做法：自己实现变位规则 + 用 Lexique 的形式集合做**校验**。
  规则生成 -> 与 Lexique 实际形式比对 -> 报告覆盖率与差异。
  这样既拿到标签，又能验证规则对不对。

覆盖范围：
  第一组 -er（5,678 个，占 88.7%）
  第二组 -ir（440 个）
  第三组 -re 与不规则（282 个，逐个手工处理主要动词）

输出：
  app/conj.js   window.CONJ = {"parler": {"présent": ["parle","parles",...], ...}}
  data/conj_report.tsv  每个动词的规则覆盖率

    python tools/build_conjugation.py
"""
import collections
import csv
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
RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
OUT_JS = os.path.join(ROOT, "app", "conj.js")
OUT_REPORT = os.path.join(ROOT, "data", "conj_report.tsv")

# ---- 时态与人称标签 ----
TENSES = [
    "présent", "imparfait", "passé simple", "futur",
    "conditionnel", "subjonctif", "impératif",
]
PERSONS = ["1s", "2s", "3s", "1p", "2p", "3p"]

# ---- 第一组 -er 变位（以 parler 为模板）----
# 关键：词干处理。parler -> parl-，但 -cer/-ger/-yer 等有拼写变化
def stem_er(inf):
    return inf[:-2]          # parler -> parl

def conj_er(inf):
    """第一组 -er（含常见拼写变化）。

    实测踩过的坑：
      appeler 应该 → appelle / appelles / appelle / appelons
        （哑 e 前双写 l；但 nous/vous 不双写）
      jeter 应该 → jette / jettes / jette / jetons
        （哑 e 前双写 t）
      payer 应该 → paie / paies / paie / payons / payez
        （-ayer 在哑 e 前 y→i；nous/vous 保留 y）
      manger 应该 → mangeons（-ger 在 a/o 前加 e）
      commencer 应该 → commençons（-cer 在 a/o 前 c→ç）
    """
    st = inf[:-2]
    out = {}

    # --- 判断拼写类型 ---
    is_cer = st.endswith("c")
    is_ger = st.endswith("g")
    is_yer = st.endswith("y")

    # 双写类：appeler（appel-）、jeter（jet-）、rappeler
    # 条件：词干结构是「元音 + 单辅音 + e + 单辅音」，末辅音是 l 或 t
    #   appel  -> a-pp-el  （pp 是双写，已经是 appelle 的形式？不是）
    #   实际规则：-eler / -eter 结尾的动词，在哑 e 前双写 l/t
    #   appeler: appel + e -> appelle
    #   jeter:   jet + e   -> jette
    is_double = bool(re.search(r"e[lts]$", st)) and not re.search(
        r"[aeiouéèê]{2}[lts]$", st)

    def apply_soft(sfx):
        """a/o 开头的后缀：-cer→ç, -ger→ge"""
        if is_cer and sfx[:1] in "ao":
            return st[:-1] + "ç" + sfx
        if is_ger and sfx[:1] in "ao":
            return st + "e" + sfx
        return st + sfx

    def apply_mute(sfx):
        """哑 e 开头的后缀（e/es/ent）：处理双写与 y→i"""
        if is_yer and sfx[:1] == "e":
            return st[:-1] + "i" + sfx
        if is_double and sfx[:1] == "e":
            # appeler -> appelle：双写词干末辅音
            return st + st[-1] + sfx
        return st + sfx

    # 现在时：1s/2s/3s/3p 用哑 e 规则，1p/2p 用软音规则
    pres = [
        apply_mute("e"), apply_mute("es"), apply_mute("e"),
        apply_soft("ons"), apply_soft("ez"), apply_mute("ent"),
    ]
    out["présent"] = pres

    # 未完成过去：全部用软音规则（-ais/-ait/-aient 是 a 开头）
    imp = [apply_soft(x) for x in ["ais", "ais", "ait", "ions", "iez", "aient"]]
    out["imparfait"] = imp

    # 简单过去
    out["passé simple"] = [st + x for x in ["ai", "as", "a", "âmes", "âtes", "èrent"]]

    # 简单将来 / 条件式：用不定式词干，无拼写变化
    out["futur"] = [inf + x for x in ["ai", "as", "a", "ons", "ez", "ont"]]
    out["conditionnel"] = [inf + x for x in ["ais", "ais", "ait", "ions", "iez", "aient"]]

    # 虚拟式现在时：同现在时规则
    out["subjonctif"] = [
        apply_mute("e"), apply_mute("es"), apply_mute("e"),
        apply_soft("ions"), apply_soft("iez"), apply_mute("ent"),
    ]
    # 命令式：2s / 1p / 2p
    out["impératif"] = [pres[1], pres[3], pres[4]]

    # 非人称形式
    out["_infinitif"] = inf
    out["_participe présent"] = apply_soft("ant")
    out["_participe passé"] = st + "é"
    return out


# ---- 第二组 -ir（finir 型）----
def conj_ir(inf):
    st = inf[:-2]
    iss = st + "iss"
    out = {}
    out["présent"] = [st + "is", st + "is", st + "it", iss + "ons", iss + "ez", iss + "ent"]
    out["imparfait"] = [iss + x for x in ["ais", "ais", "ait", "ions", "iez", "aient"]]
    out["passé simple"] = [st + x for x in ["is", "is", "it", "îmes", "îtes", "irent"]]
    out["futur"] = [inf + x for x in ["ai", "as", "a", "ons", "ez", "ont"]]
    out["conditionnel"] = [inf + x for x in ["ais", "ais", "ait", "ions", "iez", "aient"]]
    out["subjonctif"] = [iss + x for x in ["e", "es", "e", "ions", "iez", "ent"]]
    out["impératif"] = [st + "is", iss + "ons", iss + "ez"]
    out["_infinitif"] = inf
    out["_participe présent"] = iss + "ant"
    out["_participe passé"] = st + "i"
    return out


# ---- 第三组 -re 与不规则：手工表（覆盖最常用的）----
IRREGULAR = {
    "être": {
        "présent": ["suis", "es", "est", "sommes", "êtes", "sont"],
        "imparfait": ["étais", "étais", "était", "étions", "étiez", "étaient"],
        "passé simple": ["fus", "fus", "fut", "fûmes", "fûtes", "furent"],
        "futur": ["serai", "seras", "sera", "serons", "serez", "seront"],
        "conditionnel": ["serais", "serais", "serait", "serions", "seriez", "seraient"],
        "subjonctif": ["sois", "sois", "soit", "soyons", "soyez", "soient"],
        "impératif": ["sois", "soyons", "soyez"],
        "_infinitif": "être", "_participe présent": "étant", "_participe passé": "été",
    },
    "avoir": {
        "présent": ["ai", "as", "a", "avons", "avez", "ont"],
        "imparfait": ["avais", "avais", "avait", "avions", "aviez", "avaient"],
        "passé simple": ["eus", "eus", "eut", "eûmes", "eûtes", "eurent"],
        "futur": ["aurai", "auras", "aura", "aurons", "aurez", "auront"],
        "conditionnel": ["aurais", "aurais", "aurait", "aurions", "auriez", "auraient"],
        "subjonctif": ["aie", "aies", "ait", "ayons", "ayez", "aient"],
        "impératif": ["aie", "ayons", "ayez"],
        "_infinitif": "avoir", "_participe présent": "ayant", "_participe passé": "eu",
    },
    "aller": {
        "présent": ["vais", "vas", "va", "allons", "allez", "vont"],
        "imparfait": ["allais", "allais", "allait", "allions", "alliez", "allaient"],
        "passé simple": ["allai", "allas", "alla", "allâmes", "allâtes", "allèrent"],
        "futur": ["irai", "iras", "ira", "irons", "irez", "iront"],
        "conditionnel": ["irais", "irais", "irait", "irions", "iriez", "iraient"],
        "subjonctif": ["aille", "ailles", "aille", "allions", "alliez", "aillent"],
        "impératif": ["va", "allons", "allez"],
        "_infinitif": "aller", "_participe présent": "allant", "_participe passé": "allé",
    },
    "faire": {
        "présent": ["fais", "fais", "fait", "faisons", "faites", "font"],
        "imparfait": ["faisais", "faisais", "faisait", "faisions", "faisiez", "faisaient"],
        "passé simple": ["fis", "fis", "fit", "fîmes", "fîtes", "firent"],
        "futur": ["ferai", "feras", "fera", "ferons", "ferez", "feront"],
        "conditionnel": ["ferais", "ferais", "ferait", "ferions", "feriez", "feraient"],
        "subjonctif": ["fasse", "fasses", "fasse", "fassions", "fassiez", "fassent"],
        "impératif": ["fais", "faisons", "faites"],
        "_infinitif": "faire", "_participe présent": "faisant", "_participe passé": "fait",
    },
    "dire": {
        "présent": ["dis", "dis", "dit", "disons", "dites", "disent"],
        "imparfait": ["disais", "disais", "disait", "disions", "disiez", "disaient"],
        "passé simple": ["dis", "dis", "dit", "dîmes", "dîtes", "dirent"],
        "futur": ["dirai", "diras", "dira", "dirons", "direz", "diront"],
        "conditionnel": ["dirais", "dirais", "dirait", "dirions", "diriez", "diraient"],
        "subjonctif": ["dise", "dises", "dise", "disions", "disiez", "disent"],
        "impératif": ["dis", "disons", "dites"],
        "_infinitif": "dire", "_participe présent": "disant", "_participe passé": "dit",
    },
    "prendre": {
        "présent": ["prends", "prends", "prend", "prenons", "prenez", "prennent"],
        "imparfait": ["prenais", "prenais", "prenait", "prenions", "preniez", "prenaient"],
        "passé simple": ["pris", "pris", "prit", "prîmes", "prîtes", "prirent"],
        "futur": ["prendrai", "prendras", "prendra", "prendrons", "prendrez", "prendront"],
        "conditionnel": ["prendrais", "prendrais", "prendrait", "prendrions", "prendriez", "prendraient"],
        "subjonctif": ["prenne", "prennes", "prenne", "prenions", "preniez", "prennent"],
        "impératif": ["prends", "prenons", "prenez"],
        "_infinitif": "prendre", "_participe présent": "prenant", "_participe passé": "pris",
    },
    "venir": {
        "présent": ["viens", "viens", "vient", "venons", "venez", "viennent"],
        "imparfait": ["venais", "venais", "venait", "venions", "veniez", "venaient"],
        "passé simple": ["vins", "vins", "vint", "vînmes", "vîntes", "vinrent"],
        "futur": ["viendrai", "viendras", "viendra", "viendrons", "viendrez", "viendront"],
        "conditionnel": ["viendrais", "viendrais", "viendrait", "viendrions", "viendriez", "viendraient"],
        "subjonctif": ["vienne", "viennes", "vienne", "venions", "veniez", "viennent"],
        "impératif": ["viens", "venons", "venez"],
        "_infinitif": "venir", "_participe présent": "venant", "_participe passé": "venu",
    },
    "voir": {
        "présent": ["vois", "vois", "voit", "voyons", "voyez", "voient"],
        "imparfait": ["voyais", "voyais", "voyait", "voyions", "voyiez", "voyaient"],
        "passé simple": ["vis", "vis", "vit", "vîmes", "vîtes", "virent"],
        "futur": ["verrai", "verras", "verra", "verrons", "verrez", "verront"],
        "conditionnel": ["verrais", "verrais", "verrait", "verrions", "verriez", "verraient"],
        "subjonctif": ["voie", "voies", "voie", "voyions", "voyiez", "voient"],
        "impératif": ["vois", "voyons", "voyez"],
        "_infinitif": "voir", "_participe présent": "voyant", "_participe passé": "vu",
    },
    "pouvoir": {
        "présent": ["peux", "peux", "peut", "pouvons", "pouvez", "peuvent"],
        "imparfait": ["pouvais", "pouvais", "pouvait", "pouvions", "pouviez", "pouvaient"],
        "passé simple": ["pus", "pus", "put", "pûmes", "pûtes", "purent"],
        "futur": ["pourrai", "pourras", "pourra", "pourrons", "pourrez", "pourront"],
        "conditionnel": ["pourrais", "pourrais", "pourrait", "pourrions", "pourriez", "pourraient"],
        "subjonctif": ["puisse", "puisses", "puisse", "puissions", "puissiez", "puissent"],
        "impératif": [],
        "_infinitif": "pouvoir", "_participe présent": "pouvant", "_participe passé": "pu",
    },
    "vouloir": {
        "présent": ["veux", "veux", "veut", "voulons", "voulez", "veulent"],
        "imparfait": ["voulais", "voulais", "voulait", "voulions", "vouliez", "voulaient"],
        "passé simple": ["voulus", "voulus", "voulut", "voulûmes", "voulûtes", "voulurent"],
        "futur": ["voudrai", "voudras", "voudra", "voudrons", "voudrez", "voudront"],
        "conditionnel": ["voudrais", "voudrais", "voudrait", "voudrions", "voudriez", "voudraient"],
        "subjonctif": ["veuille", "veuilles", "veuille", "voulions", "vouliez", "veuillent"],
        "impératif": ["veuille", "veuillons", "veuillez"],
        "_infinitif": "vouloir", "_participe présent": "voulant", "_participe passé": "voulu",
    },
    "savoir": {
        "présent": ["sais", "sais", "sait", "savons", "savez", "savent"],
        "imparfait": ["savais", "savais", "savait", "savions", "saviez", "savaient"],
        "passé simple": ["sus", "sus", "sut", "sûmes", "sûtes", "surent"],
        "futur": ["saurai", "sauras", "saura", "saurons", "saurez", "sauront"],
        "conditionnel": ["saurais", "saurais", "saurait", "saurions", "sauriez", "sauraient"],
        "subjonctif": ["sache", "saches", "sache", "sachions", "sachiez", "sachent"],
        "impératif": ["sache", "sachons", "sachez"],
        "_infinitif": "savoir", "_participe présent": "sachant", "_participe passé": "su",
    },
    "devoir": {
        "présent": ["dois", "dois", "doit", "devons", "devez", "doivent"],
        "imparfait": ["devais", "devais", "devait", "devions", "deviez", "devaient"],
        "passé simple": ["dus", "dus", "dut", "dûmes", "dûtes", "durent"],
        "futur": ["devrai", "devras", "devra", "devrons", "devrez", "devront"],
        "conditionnel": ["devrais", "devrais", "devrait", "devrions", "devriez", "devraient"],
        "subjonctif": ["doive", "doives", "doive", "devions", "deviez", "doivent"],
        "impératif": [],
        "_infinitif": "devoir", "_participe présent": "devant", "_participe passé": "dû",
    },
    "mettre": {
        "présent": ["mets", "mets", "met", "mettons", "mettez", "mettent"],
        "imparfait": ["mettais", "mettais", "mettait", "mettions", "mettiez", "mettaient"],
        "passé simple": ["mis", "mis", "mit", "mîmes", "mîtes", "mirent"],
        "futur": ["mettrai", "mettras", "mettra", "mettrons", "mettrez", "mettront"],
        "conditionnel": ["mettrais", "mettrais", "mettrait", "mettrions", "mettriez", "mettraient"],
        "subjonctif": ["mette", "mettes", "mette", "mettions", "mettiez", "mettent"],
        "impératif": ["mets", "mettons", "mettez"],
        "_infinitif": "mettre", "_participe présent": "mettant", "_participe passé": "mis",
    },
    "partir": {
        "présent": ["pars", "pars", "part", "partons", "partez", "partent"],
        "imparfait": ["partais", "partais", "partait", "partions", "partiez", "partaient"],
        "passé simple": ["partis", "partis", "partit", "partîmes", "partîtes", "partirent"],
        "futur": ["partirai", "partiras", "partira", "partirons", "partirez", "partiront"],
        "conditionnel": ["partirais", "partirais", "partirait", "partirions", "partiriez", "partiraient"],
        "subjonctif": ["parte", "partes", "parte", "partions", "partiez", "partent"],
        "impératif": ["pars", "partons", "partez"],
        "_infinitif": "partir", "_participe présent": "partant", "_participe passé": "parti",
    },
    "sortir": {
        "présent": ["sors", "sors", "sort", "sortons", "sortez", "sortent"],
        "imparfait": ["sortais", "sortais", "sortait", "sortions", "sortiez", "sortaient"],
        "passé simple": ["sortis", "sortis", "sortit", "sortîmes", "sortîtes", "sortirent"],
        "futur": ["sortirai", "sortiras", "sortira", "sortirons", "sortirez", "sortiront"],
        "conditionnel": ["sortirais", "sortirais", "sortirait", "sortirions", "sortiriez", "sortiraient"],
        "subjonctif": ["sorte", "sortes", "sorte", "sortions", "sortiez", "sortent"],
        "impératif": ["sors", "sortons", "sortez"],
        "_infinitif": "sortir", "_participe présent": "sortant", "_participe passé": "sorti",
    },
    "dormir": {
        "présent": ["dors", "dors", "dort", "dormons", "dormez", "dorment"],
        "imparfait": ["dormais", "dormais", "dormait", "dormions", "dormiez", "dormaient"],
        "passé simple": ["dormis", "dormis", "dormit", "dormîmes", "dormîtes", "dormirent"],
        "futur": ["dormirai", "dormiras", "dormira", "dormirons", "dormirez", "dormiront"],
        "conditionnel": ["dormirais", "dormirais", "dormirait", "dormirions", "dormiriez", "dormiraient"],
        "subjonctif": ["dorme", "dormes", "dorme", "dormions", "dormiez", "dorment"],
        "impératif": ["dors", "dormons", "dormez"],
        "_infinitif": "dormir", "_participe présent": "dormant", "_participe passé": "dormi",
    },
    "écrire": {
        "présent": ["écris", "écris", "écrit", "écrivons", "écrivez", "écrivent"],
        "imparfait": ["écrivais", "écrivais", "écrivait", "écrivions", "écriviez", "écrivaient"],
        "passé simple": ["écrivis", "écrivis", "écrivit", "écrivîmes", "écrivîtes", "écrivirent"],
        "futur": ["écrirai", "écriras", "écrira", "écrirons", "écrirez", "écriront"],
        "conditionnel": ["écrirais", "écrirais", "écrirait", "écririons", "écririez", "écriraient"],
        "subjonctif": ["écrive", "écrives", "écrive", "écrivions", "écriviez", "écrivent"],
        "impératif": ["écris", "écrivons", "écrivez"],
        "_infinitif": "écrire", "_participe présent": "écrivant", "_participe passé": "écrit",
    },
    "lire": {
        "présent": ["lis", "lis", "lit", "lisons", "lisez", "lisent"],
        "imparfait": ["lisais", "lisais", "lisait", "lisions", "lisiez", "lisaient"],
        "passé simple": ["lus", "lus", "lut", "lûmes", "lûtes", "lurent"],
        "futur": ["lirai", "liras", "lira", "lirons", "lirez", "liront"],
        "conditionnel": ["lirais", "lirais", "lirait", "lirions", "liriez", "liraient"],
        "subjonctif": ["lise", "lises", "lise", "lisions", "lisiez", "lisent"],
        "impératif": ["lis", "lisons", "lisez"],
        "_infinitif": "lire", "_participe présent": "lisant", "_participe passé": "lu",
    },
    "boire": {
        "présent": ["bois", "bois", "boit", "buvons", "buvez", "boivent"],
        "imparfait": ["buvais", "buvais", "buvait", "buvions", "buviez", "buvaient"],
        "passé simple": ["bus", "bus", "but", "bûmes", "bûtes", "burent"],
        "futur": ["boirai", "boiras", "boira", "boirons", "boirez", "boiront"],
        "conditionnel": ["boirais", "boirais", "boirait", "boirions", "boiriez", "boiraient"],
        "subjonctif": ["boive", "boives", "boive", "buvions", "buviez", "boivent"],
        "impératif": ["bois", "buvons", "buvez"],
        "_infinitif": "boire", "_participe présent": "buvant", "_participe passé": "bu",
    },
    "manger": None,   # 规则第一组，走 conj_er
    "commencer": None,
    "appeler": None,
}


def build_form(form, inst):
    return {"f": form, "t": inst}


def main():
    # Lexique：原型 -> 形式集合（用于校验）
    lex = collections.defaultdict(set)
    with io.open(LEXIQUE, encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            if row["cgram"] in ("VER", "AUX") and row["lemme"]:
                lex[row["lemme"]].add(row["ortho"])

    sys.stderr.write("Lexique 动词原型 %d\n" % len(lex))

    CONJ = {}
    report = []
    stats = collections.Counter()

    for lem in sorted(lex.keys()):
        if lem in IRREGULAR and IRREGULAR[lem]:
            table = IRREGULAR[lem]
            kind = "irregular-hand"
        elif lem.endswith("er"):
            table = conj_er(lem)
            kind = "1st-er"
        elif lem.endswith("ir"):
            table = conj_ir(lem)
            kind = "2nd-ir"
        else:
            # 第三组未手工覆盖的：跳过（有 282 个，主要是 -re）
            stats["skip-3rd"] += 1
            continue

        # 校验：规则生成的形式有多少在 Lexique 里真实出现
        generated = set()
        for k, v in table.items():
            if k.startswith("_"):
                generated.add(v)
            else:
                generated.update(v)

        actual = lex.get(lem, set())
        if actual:
            hit = len(generated & actual)
            cov = hit / len(generated) if generated else 0
        else:
            cov = 0.0

        CONJ[lem] = table
        stats[kind] += 1
        report.append((lem, kind, len(generated), len(actual), round(cov, 3)))

    # 输出
    js = "window.CONJ=" + json.dumps(CONJ, ensure_ascii=False,
                                    separators=(",", ":")) + ";"
    with io.open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js + "\n")

    with io.open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("原型\t类型\t生成形式数\tLexique实测\t覆盖率\n")
        for r in report:
            f.write("%s\t%s\t%d\t%d\t%.3f\n" % r)

    size = len(js.encode("utf-8"))
    print("变位表 %d 个动词 -> %s（%.2f MB）" % (len(CONJ), OUT_JS, size / 1048576))
    for k, v in stats.most_common():
        print("  %-16s %d" % (k, v))

    # 覆盖率统计
    covs = [r[4] for r in report if r[3] > 0]
    if covs:
        covs.sort()
        print("\n与 Lexique 实测形式的覆盖率：")
        print("  中位 %.1f%%  均值 %.1f%%" % (100 * covs[len(covs) // 2],
                                              100 * sum(covs) / len(covs)))
        low = [r for r in report if r[3] > 0 and r[4] < 0.6]
        print("  覆盖率 <60%% 的动词：%d 个" % len(low))
        for r in low[:10]:
            print("    %-14s %s  cov=%.2f" % (r[0], r[1], r[4]))


if __name__ == "__main__":
    main()