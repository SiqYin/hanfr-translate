import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from guard import post_chat, assert_endpoint          # noqa: E402

PROMPT = (
    "请把下面每一行中文句子翻译成地道、自然的现代法语。"
    "严格一行对一行，只输出法语译文，不要编号和解释。"
    "输出格式：{\"s\":[\"...\"]}\n\n输入：\n"
)

SENTS = ["这张桌子很结实。", "他把钥匙放在桌子上了。", "他每天坐地铁去上班。",
         "这本书我读了三天。", "孩子们在公园里玩球。"]

assert_endpoint()
payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(SENTS))

for batch in (5, 10):
    sents = (SENTS * 4)[:batch]
    payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(sents))
    ok = 0
    t0 = time.time()
    rounds = 3
    for i in range(rounds):
        r = post_chat(PROMPT + payload, max_tokens=1500, temperature=0.1,
                      audit_tag="probe3")
        n = 0
        if r:
            j, k = r.find("{"), r.rfind("}")
            if j >= 0:
                try:
                    n = len([x for x in json.loads(r[j:k + 1])["s"] if x.strip()])
                except Exception:
                    n = 0
        ok += n
        print("  batch=%d 第%d轮: %d/%d  %.1fs" % (batch, i + 1, n, len(sents),
                                                  time.time() - t0))
        time.sleep(2)
    dt = time.time() - t0
    print("batch=%d 串行 %d 轮共 %d 句 %.0fs -> %.2f 句/s\n"
          % (batch, rounds, ok, dt, ok / dt if dt else 0))
