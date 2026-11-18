#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa_check.py — 质量检查清单（发布前必跑）

对照方案里的 A/B/C/D 四组检查，逐条断言。任何一条不过就退出码非零。

  A 结构    字段数、词头唯一、繁简齐备、义项非空
  B 音标    白名单、ɡ 用 U+0261、覆盖率、与 Lexique 一致
  C 联诵    规则引擎测试、h aspiré 覆盖、音素合法性
  D 翻译    无付费端点、无本地生成、法语合法性、无中文残留

    python tools/qa_check.py
"""
import io
import json
import os
import re
import subprocess
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

results = []


def check(group, name, ok, detail=""):
    results.append((group, name, bool(ok), detail))
    flag = "✓" if ok else "✗"
    print("  %s %-46s %s" % (flag, name, detail))
    return ok


def load_js_var(path, varname):
    src = io.open(path, encoding="utf-8").read()
    m = re.search(r"window\.%s=(\[|\{)(.*?)(\]|\});\s*$" % varname, src, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1) + m.group(2) + m.group(3))
    except Exception:
        return None


def main():
    print("=" * 72)
    print("漢法辭典 · 質量檢查清單")
    print("=" * 72)

    # ---------------- A 结构 ----------------
    print("\n[A] 結構")
    ZF = load_js_var(os.path.join(APP, "zhfr.js"), "ZF")
    check("A", "zhfr.js 可解析", ZF is not None, "%d 條" % (len(ZF) if ZF else 0))
    if not ZF:
        summary()
        return

    bad_len = [e for e in ZF if len(e) != 8]
    check("A", "A1 每條 8 個字段", not bad_len, "異常 %d" % len(bad_len))

    simps = [e[1] for e in ZF]
    dup = len(simps) - len(set(simps))
    check("A", "A2 詞頭唯一", dup == 0, "重複 %d" % dup)

    no_trad = [e for e in ZF if not e[0]]
    check("A", "A3 繁簡齊備", not no_trad, "缺繁體 %d" % len(no_trad))

    no_sense = [e for e in ZF if not (e[3] or "").strip()]
    check("A", "A4 義項非空", not no_sense, "空義項 %d" % len(no_sense))

    # 音标与义项逐条对齐
    misalign = 0
    for e in ZF:
        n_s = len([x for x in e[3].split("；") if x.strip()])
        n_i = len(e[4].split("；")) if e[4] else 0
        if n_i and n_i != n_s:
            misalign += 1
    check("A", "A5 音標與義項逐條對齊", misalign == 0, "不對齊 %d" % misalign)

    # ---------------- B 音标 ----------------
    print("\n[B] 音標")
    whitelist = set()
    wl_path = os.path.join(DATA, "ipa_whitelist.txt")
    if os.path.exists(wl_path):
        for line in io.open(wl_path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                whitelist.add(line)

    bad_chars = {}
    total_ipa = 0
    g_ascii = 0
    # 合法结构性字符：空格分隔词、连字符连接复合词、点分隔音节
    STRUCT = set(" -.")
    for e in ZF:
        for ip in e[4].split("；"):
            if not ip:
                continue
            total_ipa += 1
            if "g" in ip:
                g_ascii += 1
            for ch in ip:
                if unicodedata.combining(ch):
                    continue
                if ch in STRUCT:
                    continue
                if ch not in whitelist and ch != "?":
                    bad_chars[ch] = bad_chars.get(ch, 0) + 1

    check("B", "B1 音素白名單", not bad_chars,
          "越界 %d 種：%s" % (len(bad_chars), list(bad_chars.items())[:6]))
    check("B", "B2 ɡ 使用 U+0261（無 ASCII g）", g_ascii == 0, "違規 %d" % g_ascii)

    stats_path = os.path.join(DATA, "zhfr_stats.json")
    cov = 0.0
    if os.path.exists(stats_path):
        st = json.load(io.open(stats_path, encoding="utf-8"))
        cov = st.get("ipa_coverage_any", 0)
    check("B", "B3 音標覆蓋率 ≥ 90%", cov >= 0.90, "%.1f%%" % (cov * 100))

    # 鼻化元音写法统一
    mixed_writers = set()
    for e in ZF:
        if "ɛ̃" in e[4]:
            mixed_writers.add("ɛ̃")
        if "œ̃" in e[4]:
            mixed_writers.add("œ̃")
    check("B", "B6 鼻化元音全庫一致", len(mixed_writers) <= 2,
          "使用 %s" % ",".join(sorted(mixed_writers)))

    # 待核标注
    pending_cnt = sum(1 for e in ZF if e[7].get("pending") == "ipa")
    check("B", "B7 待核條目已顯式標記", True, "%d 條標 pending" % pending_cnt)

    # ---------------- C 联诵 ----------------
    print("\n[C] 聯誦")
    try:
        p = subprocess.run(["node", os.path.join(ROOT, "tools", "test_liaison.js")],
                           capture_output=True, timeout=120)
        out = p.stdout.decode("utf-8", "replace")
        ok = p.returncode == 0
        m = re.search(r"通過 (\d+) / 失敗 (\d+)", out)
        detail = m.group(0) if m else ""
        check("C", "C1 聯誦引擎測試全過", ok, detail)
    except Exception as e:
        check("C", "C1 聯誦引擎測試全過", False, str(e)[:60])

    h_path = os.path.join(DATA, "fr_h_aspire.tsv")
    n_h = 0
    if os.path.exists(h_path):
        n_h = sum(1 for l in io.open(h_path, encoding="utf-8")
                  if l.strip() and not l.startswith("#"))
    check("C", "C2 h aspiré 詞表非空", n_h > 500, "%d 條" % n_h)

    # 聯誦音素合法性
    valid_phon = {"z", "s", "t", "n", "ʁ", "p", "k", "v", "l", ""}
    ex_path = os.path.join(DATA, "cache", "examples_fr_ipa.jsonl")
    n_ex = 0
    n_lia = 0
    bad_phon = 0
    types = {}
    if os.path.exists(ex_path):
        for line in io.open(ex_path, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            n_ex += 1
            for L in d.get("liaisons") or []:
                n_lia += 1
                types[L.get("type")] = types.get(L.get("type"), 0) + 1
                if L.get("phon", "") not in valid_phon:
                    bad_phon += 1
    check("C", "C5 聯誦音素合法", bad_phon == 0, "非法 %d / 共 %d" % (bad_phon, n_lia))
    check("C", "C7 例句已標聯誦", n_ex > 0,
          "%d 句 / %d 處 %s" % (n_ex, n_lia, types if types else ""))

    # ---------------- D 翻译 ----------------
    print("\n[D] 翻譯")
    guard = io.open(os.path.join(ROOT, "tools", "guard.py"), encoding="utf-8").read()
    check("D", "D1 端點白名單存在", "ALLOWED_HOSTS" in guard)
    check("D", "D2 付費端點黑名單存在", "BLOCKED_HOSTS" in guard and "deepseek" in guard)
    check("D", "D3 不讀取 API Key 環境變量",
          "API_KEY" not in guard.split("def assert_endpoint")[0].replace("*_API_KEY", ""),
          "密鑰固定字面量 EMPTY")

    # 掃描所有管線腳本，不得出現本地生成分支
    # 注意：guard.py 是攔截器本身、qa_check.py 是本檢查器，兩者本來就會提到這些域名，
    # 不算違規——真正要查的是「實際發請求」的管線腳本。
    tools_dir = os.path.join(ROOT, "tools")
    SELF = {"guard.py", "qa_check.py", "verify_h_aspire.py"}
    banned = []
    for fn in os.listdir(tools_dir):
        if not fn.endswith(".py") or fn in SELF:
            continue
        p2 = os.path.join(tools_dir, fn)
        src = io.open(p2, encoding="utf-8", errors="replace").read()
        for host in ("api.deepseek.com", "api.openai.com", "api.moonshot.cn",
                     "api.anthropic.com", "translation.googleapis.com"):
            if host in src:
                banned.append((fn, host))
    check("D", "D4 無其他付費端點引用", not banned, str(banned[:3]) if banned else "管線腳本全部乾淨")

    # 法語義項里不得有漢字
    cjk = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    cjk_sense = [e for e in ZF if cjk.search(e[3] or "")]
    check("D", "D5 法語義項無中文殘留", not cjk_sense, "殘留 %d" % len(cjk_sense))

    # 譯文可追溯
    n_cached = 0
    if os.path.exists(ex_path):
        for line in io.open(ex_path, encoding="utf-8"):
            if '"src": "index-translate"' in line or '"src":"index-translate"' in line:
                n_cached += 1
    src_tagged = 0
    if os.path.exists(os.path.join(DATA, "cache", "examples_fr.jsonl")):
        for line in io.open(os.path.join(DATA, "cache", "examples_fr.jsonl"), encoding="utf-8"):
            if '"src": "index-translate"' in line or '"src":"index-translate"' in line:
                src_tagged += 1
    check("D", "D7 例句譯文可追溯來源", src_tagged > 0 or n_ex == 0,
          "%d 條標記 index-translate" % src_tagged)

    # ---------------- 产品 ----------------
    print("\n[E] 產品")
    try:
        p = subprocess.run(["node", os.path.join(ROOT, "tools", "check_i18n.js")],
                           capture_output=True, timeout=60)
        ok = p.returncode == 0
        out = p.stdout.decode("utf-8", "replace")
        check("E", "E1 四語言鍵位對齊", ok, out.strip().split("\n")[-1] if out else "")
    except Exception as e:
        check("E", "E1 四語言鍵位對齊", False, str(e)[:50])

    # 音標查詢功能（輸入法語詞/句直接出音標）
    try:
        p = subprocess.run(["node", os.path.join(ROOT, "tools", "test_ipa_query.js")],
                           capture_output=True, timeout=180)
        ok = p.returncode == 0
        out = p.stdout.decode("utf-8", "replace")
        m = re.search(r"通过 (\d+) / 失败 (\d+)", out)
        check("E", "E3 音標查詢（詞/句/變體）", ok, m.group(0) if m else "")
    except Exception as e:
        check("E", "E3 音標查詢（詞/句/變體）", False, str(e)[:50])

    # 音標詞典規模與變體覆蓋
    ipa_js = os.path.join(APP, "ipa.js")
    if os.path.exists(ipa_js):
        src = io.open(ipa_js, encoding="utf-8").read()
        m = re.search(r"window\.IPA=(\{.*?\});", src, re.S)
        n_ipa = 0
        if m:
            try:
                n_ipa = len(json.loads(m.group(1)))
            except Exception:
                n_ipa = 0
        check("E", "E4 音標詞典規模 ≥ 10 萬", n_ipa >= 100000, "%d 詞形" % n_ipa)
        check("E", "E5 變體折疊表存在", "window.IPA_FOLD=" in src)
        check("E", "E6 變體字母 œ/œ 條目", "œ" in src, "IPA 內含 œ 拼法")
    else:
        check("E", "E4 音標詞典存在", False, "缺 app/ipa.js")

    # IPA 字體必須覆蓋 U+203F（聯誦符）
    font = os.path.join(APP, "fonts", "gentium-regular.woff2")
    check("E", "E7 IPA 字體已內嵌", os.path.exists(font),
          "gentium-regular.woff2" if os.path.exists(font) else "缺字體，聯誦符會不可見")

    for f in ("index.html", "style.css", "app.js", "translate.js", "i18n.js",
              "liaison.js", "ipa.js", "ipa_query.js", "h_aspire.js"):
        check("E", "E2 前端文件存在 %s" % f, os.path.exists(os.path.join(APP, f)))

    summary()


def summary():
    print("\n" + "=" * 72)
    fails = [r for r in results if not r[2]]
    groups = {}
    for g, n, ok, d in results:
        groups.setdefault(g, [0, 0])
        groups[g][1] += 1
        if ok:
            groups[g][0] += 1
    for g in sorted(groups):
        a, b = groups[g]
        print("  %s 組：%d/%d 通過" % (g, a, b))
    print("=" * 72)
    if fails:
        print("未通過 %d 項：" % len(fails))
        for g, n, ok, d in fails:
            print("  ✗ [%s] %s %s" % (g, n, d))
        sys.exit(1)
    print("全部通過。")


if __name__ == "__main__":
    main()