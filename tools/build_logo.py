#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_logo.py — 从 WuyuqIris 品牌资产生成全尺寸 LOGO 与应用图标

来源（用户自绘，取自 BewlyIris 的 brand/ 目录）：
  wuyuqiris-icon.svg   1024x1024  圆角方形底 + 白色鸢尾纹章（黑->蓝渐变）
  wuyuqiris-mark.svg   851x1029   纯白纹章
  wuyuqiris-icon.png   2048x2048 高清位图

生成：
  app/assets/logo.svg                网页主视觉（圆形内切，与 README 一致）
  app/assets/logo-{1024..64}.png     各尺寸位图
  app/favicon.ico                    多尺寸图标
  build/icon.ico                     Windows 打包图标
  docs/logo.png                      README 顶部徽章（200px 显示）
  electron/icon.png                  Electron 窗口图标

渲染方式：
  用本机 Chrome headless 截图 SVG（汉南踩过的坑：cairosvg 缺 cairo、
  svglib 不认紧凑 transform，Chrome 最稳）。

    python tools/build_logo.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.normpath(os.path.join(ROOT, "..", "..", "03_设计资产", "logo"))
APP = os.path.join(ROOT, "app")
ASSETS = os.path.join(APP, "assets")

SIZES = [1024, 512, 256, 192, 128, 64, 48, 32]


def find_chrome():
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


CHROME = find_chrome()


def render_svg(svg_text, out_png, size, round_mask=True):
    """用 Chrome headless 把 SVG 渲染成指定尺寸 PNG。

    round_mask=True 時在 SVG 外層加一個內切圓遮罩，讓成品是正圓
    （與漢南／漢維的 README 圓形徽章口徑一致）。
    """
    if not CHROME:
        return False

    html = svg_text
    if round_mask:
        # 原 SVG 是圓角方形底；套一層圓形 clip 變成正圓
        m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg_text)
        w, h = (m.group(1), m.group(2)) if m else ("1024", "1024")
        body = re.sub(r"</?svg[^>]*>", "", svg_text, count=0)
        html = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s">'
            '<defs><clipPath id="rc"><circle cx="%s" cy="%s" r="%s"/></clipPath></defs>'
            '<g clip-path="url(#rc)">%s</g></svg>'
            % (w, h, w, h, int(w) // 2, int(h) // 2, int(w) // 2, body)
        )

    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "logo.html")
        with io.open(html_path, "w", encoding="utf-8") as f:
            f.write(
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}"
                "svg{display:block;width:%dpx;height:%dpx}</style></head><body>%s</body></html>"
                % (size, size, html))
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--default-background-color=00000000",
               "--screenshot=" + out_png,
               "--window-size=%d,%d" % (size, size),
               "file:///" + html_path.replace("\\", "/")]
        try:
            subprocess.run(cmd, check=True, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(out_png) and os.path.getsize(out_png) > 200
        except Exception as e:
            sys.stderr.write("  渲染 %dpx 失败：%s\n" % (size, e))
            return False


def make_ico(pngs, out_ico):
    """用 Pillow 合成多尺寸 .ico。"""
    try:
        from PIL import Image
    except ImportError:
        sys.stderr.write("  缺 Pillow，跳过 ico\n")
        return False
    imgs = []
    for p in pngs:
        if os.path.exists(p):
            imgs.append(Image.open(p).convert("RGBA"))
    if not imgs:
        return False
    base = max(imgs, key=lambda im: im.size[0])
    base.save(out_ico, format="ICO",
              sizes=[(s, s) for s in (256, 128, 64, 48, 32, 16)])
    return True


def main():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "electron"), exist_ok=True)

    svg_path = os.path.join(SRC_DIR, "wuyuqiris-icon.svg")
    if not os.path.exists(svg_path):
        sys.stderr.write("找不到 %s\n" % svg_path)
        raise SystemExit(1)
    svg = io.open(svg_path, encoding="utf-8").read()

    if not CHROME:
        sys.stderr.write("找不到 Chrome/Edge，无法渲染。原始 SVG 仍会被复制。\n")

    # 1) 网页主视觉：圆形版（与 README 一致）
    print("渲染圆形 logo…")
    ok_any = False
    for s in SIZES:
        out = os.path.join(ASSETS, "logo-%d.png" % s)
        if render_svg(svg, out, s, round_mask=True):
            ok_any = True
            print("  logo-%d.png" % s)

    # 2) 方形版（APP 图标用，保留圆角方形底）
    print("渲染方形 logo…")
    for s in (1024, 512, 192, 128, 64):
        out = os.path.join(ASSETS, "logo-square-%d.png" % s)
        if render_svg(svg, out, s, round_mask=False):
            print("  logo-square-%d.png" % s)

    # 3) 圆形 SVG（给网页用，避免依赖位图）
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    w, h = (m.group(1), m.group(2)) if m else ("1024", "1024")
    body = re.sub(r"</?svg[^>]*>", "", svg, count=0)
    round_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s">'
        '<title>漢法辭典</title>'
        '<defs><clipPath id="rc"><circle cx="%s" cy="%s" r="%s"/></clipPath></defs>'
        '<g clip-path="url(#rc)">%s</g></svg>'
        % (w, h, w, h, int(w) // 2, int(h) // 2, int(w) // 2, body))
    with io.open(os.path.join(ASSETS, "logo.svg"), "w", encoding="utf-8") as f:
        f.write(round_svg)
    print("  logo.svg")

    # 4) 纯白纹章（备用：浅色背景、单色场景）
    mark = os.path.join(SRC_DIR, "wuyuqiris-mark.svg")
    if os.path.exists(mark):
        shutil.copyfile(mark, os.path.join(ASSETS, "logo-mark.svg"))
        print("  logo-mark.svg")

    # 5) ico
    print("合成 ico…")
    big = [os.path.join(ASSETS, "logo-%d.png" % s) for s in (256, 128, 64, 48, 32)]
    if make_ico(big, os.path.join(APP, "favicon.ico")):
        print("  app/favicon.ico")
    if make_ico(big, os.path.join(ROOT, "build", "icon.ico")):
        print("  build/icon.ico")

    # 6) README 徽章 / Electron 图标
    for src_png, dst in [
        (os.path.join(ASSETS, "logo-512.png"), os.path.join(ROOT, "docs", "logo.png")),
        (os.path.join(ASSETS, "logo-256.png"), os.path.join(ROOT, "electron", "icon.png")),
    ]:
        if os.path.exists(src_png):
            shutil.copyfile(src_png, dst)
            print("  %s" % os.path.relpath(dst, ROOT))

    print("\n完成。%s" % ("已生成全部尺寸。" if ok_any else "未渲染位图（无 Chrome）。"))


if __name__ == "__main__":
    main()