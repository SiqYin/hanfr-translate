# NOTICE

## 数据来源与授权状态

本项目的词典数据来自三份**许可明确**的公开数据：

| 来源 | 许可 | 状态 |
|---|---|---|
| CC-CEDICT（中文词头、拼音） | CC BY-SA 4.0 | ✅ 已确认 |
| CFDICT / Chine-Informations.com（中法义项） | CC BY-SA 3.0 | ✅ 已确认 |
| Lexique 3.83（法语 IPA、词性） | CC BY-SA 4.0 | ✅ 已确认 |

**本项目不存在"授权待定"状态的数据。** 所有来源均允许商业与非商业使用，条件是署名 + 以相同方式共享。

CC BY-SA 的"相同方式共享"要求：若本项目的词典数据被修改或增补后对外分发，衍生数据同样须以 CC BY-SA 发布。**代码（MIT）与数据（CC BY-SA）分别授权**，README 与 SOURCES.md 均已说明。

## 例句

法语译文由 Index-Translate 免费公共网关生成，中文例句复用项目自有语料。译文为机器生成，未经母语者逐条审校；README 中已如实标注，不宣称"精校"。

## 第三方组件

- **CC-CEDICT** — CC BY-SA 4.0
- **CFDICT** — CC BY-SA 3.0（Chine-Informations.com, David Houstin）
- **Lexique 3.83** — CC BY-SA 4.0（New, Pallier et al., CNRS）
- **OpenCC** 繁简转换表 — Apache License 2.0
- **Index-Translate** — Apache License 2.0（bilibili）
- **Electron** — MIT License
- **Capacitor** — MIT License
- **霞鹜文楷 LXGW WenKai** 字体子集 — SIL Open Font License 1.1
- **Gentium Plus / Noto Sans** IPA 字体子集 — SIL Open Font License 1.1

## Logo

应用图标（WuyuqIris 鸢尾纹章，黑→蓝渐变底）取自本项目作者的另一个项目 [BewlyIris](https://github.com/SiqYin/BewlyIris) 的 `brand/` 目录，为**原创自绘**资产。本项目只取用 logo，不取用 BewlyIris 的代码，其自定义许可中"禁止封装成客户端"的条款不适用于品牌标识。

## 翻译服务声明

本项目**只使用** Index-Translate 免费公共网关做翻译：

- 不调用 DeepSeek 或任何付费 API
- 不读取本机任何 API Key 环境变量
- 不自行生成译文替代翻译结果

管线脚本内含端点白名单与硬拦截，见 `tools/guard.py`。

## 公开状态

本项目三端公开发布（GitHub 仓库 public、Releases 公开分发、Pages 公开访问），与本 NOTICE 声明的许可状态一致。
