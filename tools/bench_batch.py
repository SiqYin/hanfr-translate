#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_batch.py — 实测 Index-Translate 能吃多大的批

背景：
  漢南的教訓是「批 30 觸發 504」，但那是越南語 + 不同 prompt。
  不能照搬結論——必須自己測。吞吐上不去，例句量就永遠追不上漢南。

測法：
  對每個批大小跑固定次數，記錄：成功率、單次耗時、每句耗時、實際吞吐。
  只保留「成功率 100% 且每句耗時最低」的那個檔位。

    python tools/bench_batch.py
"""
import io
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
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


def bench(batch_size, rounds=3):
    ok = 0
    fail = 0
    total_ms = 0
    n_sent = 0

    for r in range(rounds):
        sents = SENTS[:batch_size]
        payload = "\n".join("%d. %s" % (k + 1, s) for k, s in enumerate(sents))
        t0 = time.time()
        raw = post_chat(PROMPT + payload, max_tokens=min(8000, batch_size * 90),
                        temperature=0.1, audit_tag="bench")
        dt = time.time() - t0

        got = 0
        if raw:
            t = raw.strip()
            i, j = t.find("{"), t.rfind("}")
            if i >= 0 and j > i:
                try:
                    d = json.loads(t[i:j + 1])
                    arr = d.get("s")
                    if isinstance(arr, list):
                        got = len([x for x in arr if str(x).strip()])
                except Exception:
                    got = 0
            if not got:
                lines = [l for l in t.split("\n") if l.strip()]
                got = len(lines) if len(lines) == len(sents) else 0

        if got == batch_size:
            ok += 1
            total_ms += dt * 1000
            n_sent += batch_size
        else:
            fail += 1

    if ok == 0:
        return {"batch": batch_size, "ok": 0, "fail": fail, "per_sent_ms": None,
                "sent_per_sec": 0}

    per_sent = total_ms / n_sent
    return {
        "batch": batch_size,
        "ok": ok,
        "fail": fail,
        "avg_call_s": round(total_ms / ok / 1000, 1),
        "per_sent_ms": round(per_sent, 0),
        "sent_per_sec": round(1000 / per_sent, 1),
    }


def main():
    assert_endpoint()
    print("批次吞吐實測（每檔 3 輪）\n")
    print("%6s %6s %6s %9s %11s %10s" % ("批次", "成功", "失敗", "單次耗時", "每句耗時", "吞吐"))
    print("-" * 58)

    results = []
    for b in (8, 16, 24, 32, 48):
        r = bench(b)
        results.append(r)
        if r["per_sent_ms"]:
            print("%6d %6d %6d %8.1fs %9.0fms %7.1f 句/s"
                  % (r["batch"], r["ok"], r["fail"], r["avg_call_s"],
                     r["per_sent_ms"], r["sent_per_sec"]))
        else:
            print("%6d %6d %6d   全部失敗" % (r["batch"], r["ok"], r["fail"]))

    # 只在成功率 100% 的檔位裡挑每句最快的
    perfect = [r for r in results if r["ok"] and r["fail"] == 0]
    if perfect:
        best = min(perfect, key=lambda r: r["per_sent_ms"])
        print("\n最佳：批次 %d，%.1f 句/s（每句 %.0fms）"
              % (best["batch"], best["sent_per_sec"], best["per_sent_ms"]))
        # 反推達到目標例句量所需時間（單進程）
        for target in (110000, 300000, 600000, 1200000):
            hrs = target / best["sent_per_sec"] / 3600
            print("  單進程做 %7d 句：%.1f 小時" % (target, hrs))
        with io.open("data/bench_batch.json", "w", encoding="utf-8") as f:
            f.write(json.dumps({"results": results, "best": best}, ensure_ascii=False, indent=2))
    else:
        print("\n沒有全成功的檔位——需降批或查網絡。")


if __name__ == "__main__":
    main()