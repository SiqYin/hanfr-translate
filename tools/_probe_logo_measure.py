import os
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOGO = r"D:\项目上下文归档\2026-11-18汉法辞典\03_设计资产\logo"
APP = r"D:\项目上下文归档\2026-11-18汉法辞典\01_源码\hanfr-app\app\assets"


def white_bbox(path):
    """白色（纹章）像素的外接框，相对于图像尺寸的比例"""
    im = Image.open(path).convert("RGBA")
    W, H = im.size
    px = im.load()
    minx, miny, maxx, maxy = W, H, -1, -1
    for y in range(0, H, max(1, H // 400)):
        for x in range(0, W, max(1, W // 400)):
            r, g, b, a = px[x, y]
            # 白色：三通道都很高且不透明
            if a > 200 and r > 230 and g > 230 and b > 230:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    if maxx < 0:
        return None
    return {
        "w_ratio": (maxx - minx + 1) / W,
        "h_ratio": (maxy - miny + 1) / H,
        "cx": (minx + maxx) / 2 / W,
        "cy": (miny + maxy) / 2 / H,
        "box": (minx, miny, maxx, maxy),
        "size": (W, H),
    }


for label, p in [
    ("原版 wuyuqiris-icon.png", os.path.join(LOGO, "wuyuqiris-icon.png")),
    ("当前 logo-1024.png", os.path.join(APP, "logo-1024.png")),
    ("当前 logo.svg 渲染 512", os.path.join(APP, "logo-512.png")),
]:
    if not os.path.exists(p):
        print("%-28s 缺文件" % label)
        continue
    r = white_bbox(p)
    if r:
        print("%-28s %dx%d  白标 %.3f x %.3f  中心 (%.3f, %.3f)"
              % (label, r["size"][0], r["size"][1],
                 r["w_ratio"], r["h_ratio"], r["cx"], r["cy"]))
    else:
        print("%-28s 未检测到白色" % label)
