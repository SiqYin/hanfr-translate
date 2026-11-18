#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_high_concurrency.py — 试更高并发，找吞吐上限

已测到并发 24 是 51.88 句/s（那一轮是冷启动，稳定后实际 25.9 句/s）。
瓶颈可能在网关，也可能在我这边的线程模型。再试 32 / 48 / 64，
看是「还能更快」还是「已经到顶」。

结论只认实测：不成功就降，不为了数字硬撑。
"""
import concurrent.futures as cf
import io
import json
import sys
import time

sys.path.insert(0, "tools")
from guard import post_chat, assert_endpoint          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROMPT = """请把下面每一行中文句子翻译成地道、自然的现代法语。
要求：
1. 严格一行对一行，输出行数与输入完全相同，不合并、不拆分、不增删。
2. 只输出法语译文，不要编号、不要解释、不要引号、不要 markdown 代码块。
3. 使用标准书面法语，避免口语缩写。
4. 保留原句的标点与语气。

输出格式：{"s": ["<译文1>", "<译文2>", ...]}

输入：
"""

S = [
    "他每天早上六点起床跑步。", "这本书我从头读到尾。", "孩子们在院子里玩沙子。",
    "她做的红烧肉特别香。", "外面风很大，别开窗户。", "我们下个月要去上海开会。",
    "他说话总是很慢。", "这个房间的采光很好。", "他们在商量搬家的事。",
    "我已经把作业写完了。", "请把灯关掉。", "这家店的面包每天现烤。",
    "他昨天换了一部新手机。", "秋天的傍晚特别凉。", "她每周去两次健身房。",
    "我们九点在车站集合。", "这条小路通向山顶。", "他把伞忘在办公室了。",
    "学生们正在准备期末考试。", "会议室在二楼最里面。", "他喜欢周末去钓鱼。",
    "这道题我想了很久。", "她给父亲寄了一些茶叶。", "火车晚点了半小时。",
    "他把眼镜落在图书馆了。", "这家公司今年扩招了。", "我妹妹明年毕业。",
    "窗外的树开花了。", "他连续开了六个小时车。", "请把这份合同签一下。",
    "他们打算把房子重新装修。", "雨停之后空气很新鲜。",
]

BATCH = 16


def run(conc, rounds=2):
    ok = fail = 0
    t0 = time.time()

    def one(_):
        sents = S[:BATCH]
        payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(sents))
        raw = post_chat(PROMPT + payload, max_tokens=2600,
                        temperature=0.1, audit_tag="bench_high")
        if not raw:
            return 0
        t = raw.strip()
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                arr = json.loads(t[i:j + 1]).get("s")
                if isinstance(arr, list):
                    n = len([x for x in arr if str(x).strip()])
                    return n if n == BATCH else 0
            except Exception:
                return 0
        return 0

    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        for got in ex.map(one, range(conc * rounds)):
            if got:
                ok += got
            else:
                fail += 1
    return ok, fail, time.time() - t0


def main():
    assert_endpoint()
    print("高并发上限实测（批 %d，每档 2 轮）\n" % BATCH)
    print("%8s %8s %8s %10s %12s" % ("并发", "成功句", "失败批", "耗时", "吞吐"))
    print("-" * 52)

    res = []
    for c in (16, 24, 32, 48):
        try:
            ok, fail, dt = run(c)
        except Exception as e:
            print("%8d 异常 %s" % (c, str(e)[:40]))
            continue
        rate = ok / dt if dt else 0
        res.append({"conc": c, "ok": ok, "fail": fail, "rate": round(rate, 2)})
        print("%8d %8d %8d %9.1fs %9.2f 句/s" % (c, ok, fail, dt, rate))

    good = [r for r in res if r["fail"] == 0 and r["ok"] > 0]
    if good:
        b = max(good, key=lambda r: r["rate"])
        print("\n零失败下最优：并发 %d，%.2f 句/s" % (b["conc"], b["rate"]))
        for t in (300000, 600000, 1200000):
            print("  %7d 句：%.1f 小时" % (t, t / b["rate"] / 3600))


if __name__ == "__main__":
    main()