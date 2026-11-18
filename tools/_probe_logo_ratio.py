import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"D:\项目上下文归档\2026-11-18汉法辞典\03_设计资产\logo"
s = io.open(BASE + r"\wuyuqiris-icon.svg", encoding="utf-8").read()

m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
W, H = float(m.group(1)), float(m.group(2))
print("viewBox: %g x %g" % (W, H))

r = re.search(r'<rect[^>]*rx="([\d.]+)"', s)
print("rect rx: %s" % (r.group(1) if r else "?"))

g = re.search(r'<g transform="translate\(([\d.]+),([\d.]+)\) scale\(([\d.]+)\)"', s)
if not g:
    print("no transform group")
    raise SystemExit

tx, ty, sc = float(g.group(1)), float(g.group(2)), float(g.group(3))
print("transform: translate(%g,%g) scale(%g)" % (tx, ty, sc))

d = re.search(r'<path d="([^"]+)"', s).group(1)
nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
xs = nums[0::2]
ys = nums[1::2]
print("path bbox: x %.0f..%.0f  y %.0f..%.0f" % (min(xs), max(xs), min(ys), max(ys)))
pw, ph = max(xs) - min(xs), max(ys) - min(ys)
print("path size: %.0f x %.0f" % (pw, ph))
print("after scale: %.0f x %.0f" % (pw * sc, ph * sc))
print("ratio of canvas: width %.4f  height %.4f" % (pw * sc / W, ph * sc / H))
print("drawn box: x %.1f..%.1f  y %.1f..%.1f"
      % (tx + min(xs) * sc, tx + max(xs) * sc, ty + min(ys) * sc, ty + max(ys) * sc))

# 中心点
cx = tx + (min(xs) + max(xs)) / 2 * sc
cy = ty + (min(ys) + max(ys)) / 2 * sc
print("mark center: (%.1f, %.1f)  canvas center (%g, %g)" % (cx, cy, W / 2, H / 2))
