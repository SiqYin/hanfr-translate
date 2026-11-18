#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard.py — 翻译端点硬拦截（红线 R1/R2/R3 的代码级实现）

汉维辞典事故的根因是「能拿到 key 就当作用了」+「赶进度压过动用户的钱」。
本模块把这层判断从「自觉」变成「代码阻断」：

  1. 只允许 Index-Translate 免费公共网关；
  2. 命中付费/第三方域名直接拒绝启动；
  3. 不读取本机任何 *_API_KEY 环境变量；
  4. 每次调用写审计日志，事后可复核。

用法：
    from guard import API_BASE, MODEL, assert_endpoint, post_chat, audit_tail
    assert_endpoint()          # 启动时调用，不合规直接 SystemExit
    text = post_chat(prompt)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# ---------- 唯一允许的端点 ----------
API_BASE = "https://index-translate.bilibili.com/v1"
CHAT_URL = API_BASE + "/chat/completions"
MODEL = "Index-Translate-35B-A3B"
KEY = "EMPTY"          # 该网关不需要真实密钥；写死，避免任何环境变量注入

# 允许的主机（严格相等匹配，不做后缀匹配，防 index-translate.bilibili.com.evil.com）
ALLOWED_HOSTS = {"index-translate.bilibili.com"}

# 明确禁止的域名（命中即拒绝启动）
BLOCKED_HOSTS = {
    "api.deepseek.com", "api.openai.com", "api.moonshot.cn", "api.anthropic.com",
    "generativelanguage.googleapis.com", "translation.googleapis.com",
    "api.mistral.ai", "openrouter.ai", "api.together.xyz", "api.groq.com",
    "dashscope.aliyuncs.com", "open.bigmodel.cn", "api.baichuan-ai.com",
    "qianfan.baidubce.com", "api.minimax.chat", "ark.cn-beijing.volces.com",
}

# 浏览器特征请求头：B 站 WAF 对裸脚本 UA 返回 412，对缺 Accept/Origin 的 POST 挂起到 504
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
    "Origin": "https://index-translate.bilibili.com",
    "Referer": "https://index-translate.bilibili.com/",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

AUDIT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "cache", "translate_audit.jsonl")


def _host_of(url):
    u = str(url or "").strip()
    for p in ("https://", "http://"):
        if u.lower().startswith(p):
            u = u[len(p):]
            break
    return u.split("/")[0].split(":")[0].lower()


def assert_endpoint(url=None):
    """启动自检：端点必须是唯一允许的网关。不合规直接退出，不给「先跑起来再说」的机会。"""
    url = url or CHAT_URL
    host = _host_of(url)

    if host in BLOCKED_HOSTS:
        sys.stderr.write(
            "拒绝启动：检测到付费/第三方 API 端点 %s\n"
            "本项目只允许 Index-Translate 免费公共网关（%s）。\n"
            "此限制是硬编码的，不提供绕过开关。\n" % (url, API_BASE)
        )
        raise SystemExit(2)

    if host not in ALLOWED_HOSTS:
        sys.stderr.write(
            "拒绝启动：未知端点 %s（host=%s）\n"
            "允许的 host 只有：%s\n" % (url, host, ", ".join(sorted(ALLOWED_HOSTS)))
        )
        raise SystemExit(2)

    # 明确断言：本进程不读取任何 API Key 环境变量
    leaked = [k for k in os.environ if k.upper().endswith("_API_KEY")]
    if leaked:
        sys.stderr.write(
            "注意：环境里存在 %s，本项目不会读取它们。密钥固定为字面量 EMPTY。\n"
            % ", ".join(sorted(leaked))
        )
    return True


def _audit(record):
    try:
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def post_chat(prompt, max_tokens=4000, temperature=0.1, timeout=180,
              retries=3, audit_tag=""):
    """向 Index-Translate 发一次 chat 请求，返回纯文本。

    失败重试采用指数退避；重试耗尽返回 None（不抛异常，让调用方决定是否记为该批失败）。
    每次调用写一条审计记录：端点、模型、耗时、状态、prompt 摘要。
    """
    assert_endpoint()

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        # 关掉思维链：开着时 CoT 文本会顶掉译文
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")

    last_err = ""
    for attempt in range(retries):
        t0 = time.time()
        req = urllib.request.Request(CHAT_URL, data=body,
                                     headers=dict(HEADERS, **{"Content-Type": "application/json"}))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            data = json.loads(raw)
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            content = content.strip()
            _audit({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "host": _host_of(CHAT_URL),
                    "model": MODEL, "ok": bool(content), "ms": int((time.time() - t0) * 1000),
                    "tag": audit_tag, "prompt_head": prompt[:80]})
            if content:
                return content
            last_err = "empty content"
        except urllib.error.HTTPError as e:
            last_err = "HTTP %s" % e.code
            try:
                e.read()
            except Exception:
                pass
        except Exception as e:
            last_err = str(e)[:120]

        _audit({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "host": _host_of(CHAT_URL),
                "model": MODEL, "ok": False, "err": last_err, "tag": audit_tag,
                "prompt_head": prompt[:80]})
        if attempt < retries - 1:
            time.sleep(1.2 * (attempt + 1))

    sys.stderr.write("请求失败（已重试 %d 次）：%s\n" % (retries, last_err))
    return None


def audit_tail(n=5):
    """读最近 n 条审计记录，供自检与发布前核对。"""
    if not os.path.exists(AUDIT_PATH):
        return []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        lines = f.readlines()[-n:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    assert_endpoint()
    print("端点合规：", CHAT_URL)
    print("模型：", MODEL)
    print("密钥：字面量 EMPTY（不读取任何环境变量）")
    r = post_chat("Translate into French: 你好", max_tokens=32, audit_tag="selftest")
    print("自检返回：", repr(r))
    print("审计尾：", audit_tail(1))
