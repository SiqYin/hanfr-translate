#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_concurrency.py — 实测并发上限

單進程批 16 只有 2.3 句/s，做 30 萬句要 36 小時，不現實。
並發是唯一可用的放大手段，但共享網關會限流——必須找到「吞吐最高且不失敗」的並發數。

測法：固定批大小 16，逐步提高並發 worker 數，量每個檔位的實際吞吐與失敗率。

    python tools/bench_concurrency.py
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

SENTS = [
    "我今天早上七点起床。", "他每天坐地铁去上班。", "这本书我读了三天。",
    "孩子们在公园里玩球。", "她做的菜很好吃。", "外面下雨了，记得带伞。",
    "我们下周要去北京出差。", "他说话声音很小。", "这个房间有两个窗户。",
    "他们在讨论明年的计划。", "我已经吃过晚饭了。", "请把门关上。",
    "这家店的咖啡很香。", "他昨天买了一辆新车。", "秋天的树叶变黄了。",
    "她每天练习弹钢琴。", "我们八点钟在门口见面。", "这条河冬天会结冰。",
    "他把钥匙放在桌子上了。", "学生们正在准备考试。", "会议室在三楼。",
    "他喜欢在周末爬山。", "这道题很难，我不会做。", "她给妈妈打了一个电话。",
    "飞机晚点了两个小时。", "他把钱包落在出租车上了。", "这家公司今年招了很多人。",
    "我弟弟今年上大学。", "窗外的景色很美。", "他连续工作了十二个小时。",
    "请把这份文件复印三份。", "他们打算搬到城南去住。",
]

BATCH = 16


def one_round(nbatch):
    """發 nbatch 個批，返回 (成功句數, 失敗批數, 耗時)"""
    t0 = time.time()
    ok_sent = 0
    fail = 0

    def work(_k):
        sents = SENTS[:BATCH]
        payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(sents))
        raw = post_chat(PROMPT + payload, max_tokens=2600,
                        temperature=0.1, audit_tag="bench_conc")
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
                pass
        return 0

    with cf.ThreadPoolExecutor(max_workers=nbatch) as ex:
        for got in ex.map(work, range(nbatch)):
            if got:
                ok_sent += got
            else:
                fail += 1

    return ok_sent, fail, time.time() - t0


def main():
    assert_endpoint()
    print("並發吞吐實測（批 %d，每檔跑 1 輪）\n" % BATCH)
    print("%8s %8s %8s %10s %12s" % ("並發", "成功句", "失敗批", "耗時", "吞吐"))
    print("-" * 52)

    results = []
    for conc in (4, 8, 12, 16, 24):
        nbatch = conc * 2
        try:
            ok, fail, dt = one_round(nbatch)
        except Exception as e:
            print("%8d 異常 %s" % (conc, str(e)[:40]))
            continue
        rate = ok / dt if dt else 0
        results.append({"conc": conc, "ok": ok, "fail": fail,
                        "sec": round(dt, 1), "rate": round(rate, 2)})
        print("%8d %8d %8d %9.1fs %9.2f 句/s  (%.1f%% 成功)"
              % (conc, ok, fail, dt, rate, 100 * ok / max(1, ok + fail * BATCH)))

    good = [r for r in results if r["fail"] == 0 and r["ok"] > 0]
    pool = good if good else [r for r in results if r["ok"] > 0]
    if not pool:
        print("\n全部失敗，無法判定。")
        return

    best = max(pool, key=lambda r: r["rate"])
    print("\n最佳並發：%d，%.2f 句/s" % (best["conc"], best["rate"]))
    for target in (110000, 300000, 600000, 1200000):
        hrs = target / best["rate"] / 3600
        print("  做 %7d 句：%.1f 小時" % (target, hrs))

    with io.open("data/bench_concurrency.json", "w", encoding="utf-8") as f:
        f.write(json.dumps({"results": results, "best": best}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()