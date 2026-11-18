import io
import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from guard import post_chat, assert_endpoint          # noqa: E402

PROMPT = """请把下面每一行中文句子翻译成地道、自然的现代法语。
要求：
1. 严格一行对一行，输出行数与输入完全相同，不合并、不拆分、不增删。
2. 只输出法语译文，不要编号、不要解释、不要引号、不要 markdown 代码块。
3. 使用标准书面法语，避免口语缩写。
4. 保留原句的标点与语气。

输出格式：{"s": ["<译文1>", "<译文2>", ...]}

输入：
"""

# 用真实语料，包含新造的字母词/生僻字句（可能就是它们让模型返回异常）
cases = {
    "普通句": ["今天的天气很好。", "他在公园里散步。"],
    "字母词": ["C盘的容量已经不够了。", "他把文件存在C盘里。"],
    "生僻字": ["㑇是古代的一种器物。", "䍃这个字现在已经很少用了。"],
    "数字词": ["10月的时候我们会放假。", "他住在42街。"],
    "混合": ["今天的天气很好。", "C盘的容量已经不够了。", "㑇是古代的一种器物。"],
}

assert_endpoint()

for name, sents in cases.items():
    payload = "\n".join("%d. %s" % (i + 1, s) for i, s in enumerate(sents))
    t0 = time.time()
    raw = post_chat(PROMPT + payload, max_tokens=1500, temperature=0.1,
                    audit_tag="probe")
    dt = time.time() - t0
    ok = None
    if raw:
        t = raw.strip()
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                arr = json.loads(t[i:j + 1]).get("s")
                if isinstance(arr, list):
                    ok = len([x for x in arr if str(x).strip()])
            except Exception as e:
                ok = "JSON坏:%s" % str(e)[:30]
        else:
            lines = [l for l in t.split("\n") if l.strip()]
            ok = "无JSON,行数=%d" % len(lines)
    print("%-8s 期望%d 得到 %s  %.1fs" % (name, len(sents), ok, dt))
    if raw and not isinstance(ok, int):
        print("     原始返回前 160 字: %r" % raw[:160])
    time.sleep(1.0)
