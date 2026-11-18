import io
import json
import sys

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from guard import post_chat, assert_endpoint          # noqa: E402

PROMPT = (
    "请把下面每一行中文句子翻译成地道、自然的现代法语。"
    "要求：\n"
    "1. 严格一行对一行，输出行数与输入完全相同，不合并、不拆分、不增删。\n"
    "2. 只输出法语译文，不要编号、不要解释、不要引号、不要 markdown 代码块。\n"
    "3. 使用标准书面法语，避免口语缩写。\n"
    "4. 保留原句的标点与语气。\n"
    "5. 若某行无法翻译，该行留空，不要编造内容。\n\n"
    "输出格式：{\"s\": [\"<译文1>\", \"<译文2>\", ...]}\n\n"
    "输入：\n"
)

# 取真实待译句子
rows = []
with io.open("data/corpus_zh.jsonl", encoding="utf-8") as f:
    for line in f:
        if len(rows) >= 8:
            break
        if line.strip():
            rows.append(json.loads(line))

assert_endpoint()

for n in (1, 2, 4):
    batch = rows[:n]
    payload = "\n".join("%d. %s" % (i + 1, d["s"]) for i, d in enumerate(batch))
    raw = post_chat(PROMPT + payload, max_tokens=1200, temperature=0.1,
                    audit_tag="probe4")
    print("=== 批 %d ===" % n)
    for d in batch:
        print("   IN:", d["s"])
    print("   RAW:", repr((raw or "")[:400]))
    ok = None
    if raw:
        j, k = raw.find("{"), raw.rfind("}")
        if j >= 0:
            try:
                arr = json.loads(raw[j:k + 1]).get("s")
                ok = len(arr) if isinstance(arr, list) else "no-s"
            except Exception as e:
                ok = "json-err:%s" % str(e)[:40]
        else:
            ok = "no-json"
    print("   解析:", ok, "\n")
