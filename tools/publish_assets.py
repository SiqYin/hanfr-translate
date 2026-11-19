#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_assets.py — 发布资产到 GitHub Release（固定文件名）

为什么用固定文件名：
  README 里的下载链接指向 /releases/latest/download/<固定名>，
  这样每次发版都不需要改 README。
  若用带版本号的文件名（HanFrDict-1.0.1-android.apk），
  latest 链接会 404——v1.0.1 就踩过这个坑，补传了一次。

    python tools/publish_assets.py 1.0.2
    python tools/publish_assets.py 1.0.2 --dry-run
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.normpath(os.path.join(ROOT, "..", "..", "06_发布产物"))
REPO = "SiqYin/hanfr-translate"

# 固定文件名 -> 源文件（源文件带版本号，上传时改成固定名）
ASSETS = [
    ("HanFrDict-setup.exe", "HanFrDict-setup-v{v}.exe"),
    ("HanFrDict-android.apk", "HanFrDict-{v}-android.apk"),
    ("HanFrDict-web.zip", "HanFrDict-{v}-web.zip"),
]


def get_token():
    """取 GitHub token。

    优先用环境变量 GH_TOKEN / GITHUB_TOKEN；
    否则从 git 凭据库取（注意：git credential fill 需要 stdin 明确给空行，
    且不能继承父进程 stdin，否则会一直等输入——实测超时 30s）。
    """
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v.strip()

    import subprocess
    try:
        p = subprocess.run(
            ["git", "credential", "fill"],
            input=b"protocol=https\nhost=github.com\n\n",
            capture_output=True, timeout=20,
            stdin=subprocess.PIPE)
        for line in p.stdout.decode("utf-8", "replace").splitlines():
            if line.startswith("password="):
                return line[len("password="):].strip()
    except Exception as e:
        sys.stderr.write("取凭据失败：%s\n" % e)
    return ""


def api(url, token, method="GET", data=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data, method=method, headers={
        "User-Agent": "hanfr-publish",
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": ctype,
    })
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    v = args.version.lstrip("v")

    token = get_token()
    if not token:
        sys.stderr.write("未取得 GitHub token\n")
        raise SystemExit(1)

    tag = "v" + v
    try:
        rel = api("https://api.github.com/repos/%s/releases/tags/%s" % (REPO, tag), token)
    except urllib.error.HTTPError as e:
        sys.stderr.write("取 Release %s 失败：HTTP %s\n" % (tag, e.code))
        raise SystemExit(1)

    print("Release %s (id=%s)" % (tag, rel["id"]))
    existing = {a["name"]: a["id"] for a in rel.get("assets", [])}

    for fixed, pat in ASSETS:
        src = os.path.join(ART, pat.format(v=v))
        if not os.path.exists(src):
            print("  跳过 %s：缺 %s" % (fixed, os.path.basename(src)))
            continue

        # 同名旧资产先删，否则同 tag 内无法重复上传同名文件
        if fixed in existing:
            if args.dry_run:
                print("  [dry] 删旧 %s" % fixed)
            else:
                try:
                    api("https://api.github.com/repos/%s/releases/assets/%d"
                        % (REPO, existing[fixed]), token, method="DELETE")
                    print("  已删旧资产 %s" % fixed)
                except Exception as e:
                    sys.stderr.write("  删旧失败 %s: %s\n" % (fixed, e))

        if args.dry_run:
            print("  [dry] 上传 %s <- %s" % (fixed, os.path.basename(src)))
            continue

        with io.open(src, "rb") as f:
            blob = f.read()
        url = ("https://uploads.github.com/repos/%s/releases/%d/assets?name=%s"
               % (REPO, rel["id"], urllib.parse.quote(fixed)))
        try:
            req = urllib.request.Request(url, data=blob, method="POST", headers={
                "User-Agent": "hanfr-publish",
                "Authorization": "token " + token,
                "Content-Type": "application/octet-stream",
            })
            with urllib.request.urlopen(req, timeout=1800) as r:
                a = json.loads(r.read().decode("utf-8"))
            print("  ✓ %s  %.1f MB" % (fixed, a["size"] / 1048576))
        except Exception as e:
            sys.stderr.write("  ✗ %s: %s\n" % (fixed, e))

    print("\n固定下载链接（始终指向 latest）：")
    for fixed, _ in ASSETS:
        print("  https://github.com/%s/releases/latest/download/%s" % (REPO, fixed))


if __name__ == "__main__":
    main()
