#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_version.py — 统一各处的版本号

版本号分散在四处，漏改会在更新检测里比对错版本（汉南 v1.5.7 就踩过）：
  package.json              version
  app/app.js                APP_VERSION（前端更新检测用）
  android/app/build.gradle  versionName / versionCode
  app/data/meta.js          可选，本项目的版本信息

    python tools/set_version.py 1.0.0
"""
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


def set_package(ver):
    p = os.path.join(ROOT, "package.json")
    s = io.open(p, encoding="utf-8").read()
    s2 = re.sub(r'"version":\s*"[^"]*"', '"version": "%s"' % ver, s, count=1)
    io.open(p, "w", encoding="utf-8").write(s2)
    return s2 != s


def set_app_js(ver):
    p = os.path.join(ROOT, "app", "app.js")
    s = io.open(p, encoding="utf-8").read()
    if re.search(r"APP_VERSION\s*=", s):
        s2 = re.sub(r'APP_VERSION\s*=\s*"[^"]*"', 'APP_VERSION = "%s"' % ver, s)
    else:
        # 没有就插入到 IIFE 开头
        s2 = s.replace('"use strict";',
                       '"use strict";\n\n  var APP_VERSION = "%s";' % ver, 1)
    io.open(p, "w", encoding="utf-8").write(s2)
    return True


def set_gradle(ver):
    p = os.path.join(ROOT, "android", "app", "build.gradle")
    if not os.path.exists(p):
        return False
    s = io.open(p, encoding="utf-8").read()
    major, minor, patch = [int(x) for x in ver.split(".")]
    code = major * 10000 + minor * 100 + patch
    s = re.sub(r"versionCode\s+\d+", "versionCode %d" % code, s)
    s = re.sub(r'versionName\s+"[^"]*"', 'versionName "%s"' % ver, s)
    io.open(p, "w", encoding="utf-8").write(s)
    return True


def set_meta(ver, entries=None):
    p = os.path.join(ROOT, "app", "data", "meta.js")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    meta = {"version": ver}
    if entries is not None:
        meta["entries"] = entries
    io.open(p, "w", encoding="utf-8").write(
        "window.LEX_META=%s;\n" % json.dumps(meta, ensure_ascii=False))
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/set_version.py 1.0.0")
        raise SystemExit(1)
    ver = sys.argv[1]

    # 词条数（写进 meta，前端页脚用）
    n = None
    p = os.path.join(ROOT, "app", "zhfr.js")
    if os.path.exists(p):
        src = io.open(p, encoding="utf-8").read()
        m = re.search(r"window\.ZF=(\[.*\]);\s*$", src, re.S)
        if m:
            try:
                n = len(json.loads(m.group(1)))
            except Exception:
                pass

    print("版本号 -> %s" % ver)
    print("  package.json      %s" % ("已更新" if set_package(ver) else "失败"))
    print("  app/app.js        %s" % ("已更新" if set_app_js(ver) else "失败"))
    print("  android/gradle    %s" % ("已更新" if set_gradle(ver) else "无此文件"))
    print("  app/data/meta.js  %s" % ("已更新" if set_meta(ver, n) else "失败"))
    if n:
        print("  词条数            %d" % n)


if __name__ == "__main__":
    main()