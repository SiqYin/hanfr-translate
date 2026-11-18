import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

z = io.open("app/zhfr.js", encoding="utf-8").read()
ZF = json.loads(re.search(r"window\.ZF=(\[.*\]);\s*$", z, re.S).group(1))

for e in ZF:
    if e[1] == "一":
        print("一 的 e[6] =", json.dumps(e[6], ensure_ascii=False)[:400])
        break

for w in ("丁", "七", "美丽", "桌子"):
    for e in ZF:
        if e[1] == w:
            ex = e[6]
            first = ex[0] if isinstance(ex[0], list) else ex
            print("%s: %s" % (w, first[0] if first else ""))
            break

bad_str = "这张" + "一很结实"
print("文件中是否含该病句:", bad_str)
print("  实际出现次数:", z.count(bad_str))
