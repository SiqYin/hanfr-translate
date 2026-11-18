#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attach_example_ipa.py — 给法语句标音标 + 联诵

输入：data/cache/examples_fr.jsonl（make_examples.py 产出）
输出：data/cache/examples_fr_ipa.jsonl
    {"zh","zh_sent","fr","fr_tokens","fr_ipa","liaisons","pending"}

两步：
  1. 逐词查 Lexique383 拿 IPA（经 lexique_phon_map 转真 IPA）；
     查不到的词写 "?"，并把整句标 pending —— 不猜。
  2. 调 app/liaison.js 的判定引擎（Node 子进程），保证前后端同一套规则。

为什么要调 Node：
  联诵规则只应该有一份实现。Python 再写一遍必然与前端漂移，
  所以这里直接跑 app/liaison.js，与浏览器执行时用的是同一份代码。

    python tools/attach_example_ipa.py
"""
import io
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nasal_style import convert_nfc          # noqa: E402

RAW = os.path.normpath(os.path.join(ROOT, "..", "..", "02_数据管线", "原始数据"))
LEXIQUE = os.path.join(RAW, "Lexique383.tsv")
PHON_MAP = os.path.join(ROOT, "data", "lexique_phon_map.json")
H_ASPIRE = os.path.join(ROOT, "data", "fr_h_aspire.tsv")
SRC = os.path.join(ROOT, "data", "cache", "examples_fr.jsonl")
OUT = os.path.join(ROOT, "data", "cache", "examples_fr_ipa.jsonl")

# 閉類詞的確定音標（Lexique 未必收錄，但這些讀音沒有爭議）
CLOSED = {
    "le": "lə", "la": "la", "les": "le", "l'": "l", "un": "œ̃", "une": "yn",
    "des": "de", "du": "dy", "de": "də", "d'": "d", "au": "o", "aux": "o",
    "à": "a", "et": "e", "ou": "u", "où": "u", "en": "ɑ̃", "y": "i",
    "ne": "nə", "n'": "n", "se": "sə", "s'": "s", "ce": "sə", "c'": "s",
    "que": "kə", "qu'": "k", "qui": "ki", "quoi": "kwa", "dont": "dɔ̃",
    "je": "ʒə", "j'": "ʒ", "tu": "ty", "nous": "nu", "vous": "vu",
    "il": "il", "elle": "ɛl", "ils": "il", "elles": "ɛl", "on": "ɔ̃",
    "me": "mə", "te": "tə", "lui": "lɥi", "leur": "lœʁ", "leurs": "lœʁ",
    "mon": "mɔ̃", "ma": "ma", "mes": "me", "ton": "tɔ̃", "ta": "ta", "tes": "te",
    "son": "sɔ̃", "sa": "sa", "ses": "se", "notre": "nɔtʁ", "votre": "vɔtʁ",
    "nos": "no", "vos": "vo", "est": "ɛ", "c'est": "sɛ", "n'est": "nɛ",
    "sont": "sɔ̃", "ont": "ɔ̃", "font": "fɔ̃", "vont": "vɔ̃",
    "très": "tʁɛ", "plus": "ply", "moins": "mwɛ̃", "tout": "tu",
}

PUNCT = re.compile(r"^[.,;:!?«»\"'…\-–—()\[\]]+$")


def load_phon_map():
    with io.open(PHON_MAP, encoding="utf-8") as f:
        return json.load(f)


def lex_to_ipa(code, pmap):
    out = []
    for c in code or "":
        v = pmap.get(c)
        if v is None:
            return None
        out.append(v)
    # 鼻化元音改真实发音标法，与词库/音标词典保持一致
    return convert_nfc("".join(out))


def load_lexique():
    rec = {}
    with io.open(LEXIQUE, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        i_o, i_p = hdr.index("ortho"), hdr.index("phon")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(i_o, i_p):
                continue
            o, ph = p[i_o].strip(), p[i_p].strip()
            if o and ph and o not in rec:
                rec[o] = ph
    return rec


def tokenize(fr):
    """法語分詞：保留標點為獨立 token，便於聯誦判定跳過。"""
    toks = []
    for m in re.finditer(r"([A-Za-zÀ-ÿŒœÆæ']+(?:-[A-Za-zÀ-ÿŒœÆæ']+)*)|([^\sA-Za-zÀ-ÿŒœÆæ']+)", fr):
        if m.group(1):
            toks.append(m.group(1))
        elif m.group(2):
            toks.append(m.group(2))
    return toks


def word_ipa(w, lex, pmap):
    lw = w.lower().strip("'")
    # 省音缩合：d'un -> d + un
    m = re.match(r"^([dljmnstcçq]|qu)'(.+)$", lw, re.I)
    if m:
        head, tail = m.group(1).lower(), m.group(2)
        tail_ipa = word_ipa(tail, lex, pmap)
        if tail_ipa:
            return head + tail_ipa if head in ("d", "l", "n", "s", "t", "m", "j") else tail_ipa
    # 连字符复合词
    if "-" in lw:
        parts = [word_ipa(p, lex, pmap) for p in lw.split("-") if p]
        if all(parts) and parts:
            return "-".join(parts)
        return None
    if lw in lex:
        return lex_to_ipa(lex[lw], pmap)
    if lw in CLOSED:
        return CLOSED[lw]
    # 复数/变位回落
    if lw.endswith("s") and lw[:-1] in lex:
        ipa = lex_to_ipa(lex[lw[:-1]], pmap)
        if ipa:
            return ipa
    if lw.endswith("es") and lw[:-2] in lex:
        ipa = lex_to_ipa(lex[lw[:-2]], pmap)
        if ipa:
            return ipa
    return None


def mark_liaisons(tokens, fr_ipa, liaisons):
    """把联诵直接标进音标与句子里。

    用户要求：**联诵直接标在音标上**，不是另起一块说明。
    做法：
      音标  /səsi ɛst œ̃ livʁ/  ->  /səsi ɛst‿œ̃ livʁ/
      句子  Ceci est un livre.  ->  Ceci est‿un livre.
      禁止  les | héros 的联诵处用 | 表示，并保持不合并读音。

    用 U+203F (undertie ‿) 表示联诵，这是国际音标与法语教学的标准符号。

    下标对齐是这里最容易出错的地方：token 与音标按位置一一对应
    （标点在两边都保留同一位置），所以直接用 token 下标访问音标下标。
    """
    if not fr_ipa:
        return "", ""
    parts = fr_ipa.split(" ")
    toks = list(tokens)

    # 下标对齐的关键：
    #   tokens 里有标点（« » , . 等），音标里也有——但音标里的标点不一定同位置
    #   （« sh ǐ » 里的 ? 占位会让长度不同）。
    # 做法：只用「非标点词」的序号来定位，把第 k 个实词映射到音标里的第 k 个非标点片段。
    def is_punct(s):
        s = str(s or "").strip()
        return (not s) or bool(PUNCT.match(s))

    # 建：实词序号 -> 音标下标
    word_idx = [i for i, t in enumerate(toks) if not is_punct(t)]
    # 音标片段里，排除纯标点
    ipa_word_pos = [i for i, p in enumerate(parts) if p and not re.fullmatch(r"[«»,.;:!?¡¿…—–-]", p)]

    if len(word_idx) != len(ipa_word_pos):
        # 对不齐：放弃内联标记，返回原音标（宁可不标，也不错标）
        fr_out = " ".join(str(t) for t in toks)
        fr_out = re.sub(r"\s+([.,;:!?])", r"\1", fr_out).strip()
        return fr_out, fr_ipa

    tok2ipa = {w: p for w, p in zip(word_idx, ipa_word_pos)}

    marked_ipa = list(parts)
    marked_toks = list(toks)

    for L in sorted(liaisons, key=lambda x: -x["i"]):
        ti = L["i"]
        ti_next = ti + 1
        if ti < 0 or ti_next >= len(toks):
            continue
        left = str(toks[ti] or "").strip()
        right = str(toks[ti_next] or "").strip()
        if is_punct(left) or is_punct(right):
            continue
        if not re.match(r"^[aeiouyàâäéèêëîïôöùûüœæh]", right.lower()):
            continue

        fi = tok2ipa.get(ti)
        if fi is None or fi >= len(marked_ipa):
            continue

        if L["type"] == "interdite":
            marked_ipa[fi] = marked_ipa[fi] + " |"
            marked_toks[ti] = marked_toks[ti] + " |"
        else:
            marked_ipa[fi] = marked_ipa[fi] + "\u203F"
            marked_toks[ti] = marked_toks[ti] + "\u203F"

    ipa_out = " ".join(marked_ipa)
    ipa_out = ipa_out.replace("\u203F ", "\u203F").replace(" \u203F", "\u203F")
    ipa_out = re.sub(r"\s+([.,;:!?])", r"\1", ipa_out)
    ipa_out = re.sub(r"\s+", " ", ipa_out).strip()

    fr_out = " ".join(marked_toks)
    fr_out = fr_out.replace("\u203F ", "\u203F").replace(" \u203F", "\u203F")
    fr_out = re.sub(r"\s+([.,;:!?])", r"\1", fr_out)
    fr_out = re.sub(r"\s+", " ", fr_out).strip()
    return fr_out, ipa_out


NODE_HELPER = r"""
const path = require("path");
const fs = require("fs");
const FRL = require(process.argv[2]);
const hAspire = new Set();
const tsv = process.argv[3];
if (fs.existsSync(tsv)) {
  for (const line of fs.readFileSync(tsv, "utf8").split("\n")) {
    if (!line || line.startsWith("#")) continue;
    const w = line.split("\t")[0].trim();
    if (w) hAspire.add(w.toLowerCase());
  }
}
let buf = "";
process.stdin.on("data", d => buf += d);
process.stdin.on("end", () => {
  const items = JSON.parse(buf);
  const out = items.map(it => {
    const lia = FRL.annotate(it.tokens, { hAspire });
    // 句音标：只做「不規則詞整詞替換」（c'est /sɛ/ -> /sɛt/），
    // 联诵标记 ‿ 由 Python 侧 mark_liaisons() 统一加，
    // 这样句子与音标用的是同一套下标，不会错位。
    let applied = it.ipa || "";
    try {
      applied = FRL.applyToIpa(it.ipa || "", lia, it.tokens);
    } catch (e) {
      applied = it.ipa || "";
    }
    return { liaisons: lia, ipa: applied };
  });
  process.stdout.write(JSON.stringify(out));
});
"""


def run_node_liaison(items):
    helper = os.path.join(ROOT, "tools", "_liaison_helper.cjs")
    with io.open(helper, "w", encoding="utf-8") as f:
        f.write(NODE_HELPER)
    try:
        p = subprocess.run(
            ["node", helper, os.path.join(ROOT, "app", "liaison.js"), H_ASPIRE],
            input=json.dumps(items).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if p.returncode != 0:
            sys.stderr.write("node 失败：%s\n" % p.stderr.decode("utf-8", "replace")[:400])
            return None
        return json.loads(p.stdout.decode("utf-8"))
    finally:
        try:
            os.remove(helper)
        except OSError:
            pass


def main():
    if not os.path.exists(SRC):
        sys.stderr.write("缺少 %s，先跑 tools/make_examples.py\n" % SRC)
        raise SystemExit(1)

    pmap = load_phon_map()
    lex = load_lexique()
    sys.stderr.write("Lexique %d / 音素映射 %d\n" % (len(lex), len(pmap)))

    rows = []
    with io.open(SRC, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    sys.stderr.write("例句 %d 条\n" % len(rows))

    prepared = []
    for r in rows:
        fr = r.get("fr") or ""
        toks = tokenize(fr)
        ipas = []
        n_ok = n_tot = 0
        for t in toks:
            if PUNCT.match(t):
                ipas.append(t)          # 标点原样保留，不参与音标
                continue
            n_tot += 1
            ip = word_ipa(t, lex, pmap)
            if ip:
                ipas.append(ip)
                n_ok += 1
            else:
                ipas.append("?")
        prepared.append({
            "tokens": [t for t in toks],
            "ipas": ipas,
            "row": r,
            "n_ok": n_ok,
            "n_tot": n_tot,
        })

    # 分批送 Node 做联诵判定
    sys.stderr.write("联诵判定中…\n")
    CH = 2000
    all_res = []
    for i in range(0, len(prepared), CH):
        chunk = prepared[i:i + CH]
        res = run_node_liaison([
            {"tokens": c["tokens"],
             "ipa": " ".join(x for x in c["ipas"] if x)}
            for c in chunk
        ])
        if res is None:
            sys.stderr.write("联诵判定失败，中止\n")
            raise SystemExit(1)
        all_res.extend(res)

    out_rows = []
    n_pending = 0
    for p, res in zip(prepared, all_res):
        r = p["row"]
        lia = res.get("liaisons") or []
        fr_ipa = res.get("ipa") or ""
        if p["n_ok"] < p["n_tot"]:
            n_pending += 1

        # 聯誦直接標在音標上（不是另起一塊說明）：
        #   法語  : Ceci est‿un livre.
        #   音標  : /səsi ɛst‿œ̃ livʁ/
        #   interdite 用 | 表示：/le | e.ʁo/
        fr_marked, ipa_marked = mark_liaisons(p["tokens"], fr_ipa, lia)

        out_rows.append({
            "zh": r.get("zh"),
            "zh_sent": r.get("zh_sent"),
            "fr": r.get("fr"),
            "fr_marked": fr_marked,
            "fr_tokens": p["tokens"],
            "fr_ipa": fr_ipa,
            "ipa_marked": ipa_marked,
            "liaisons": lia,
            "pending": "ipa" if p["n_ok"] < p["n_tot"] else "",
        })

    with io.open(OUT, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_lia = sum(len(r["liaisons"]) for r in out_rows)
    types = {}
    for r in out_rows:
        for L in r["liaisons"]:
            types[L["type"]] = types.get(L["type"], 0) + 1
    print("写出 %d 条 -> %s" % (len(out_rows), OUT))
    print("联诵标注 %d 处：%s" % (n_lia, types))
    print("音标不完整 %d 条（%.1f%%）" % (n_pending, 100 * n_pending / max(1, len(out_rows))))


if __name__ == "__main__":
    main()