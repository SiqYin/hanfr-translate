# 数据来源与许可

> 最后更新：2026-11-18　｜　本项目所有第三方数据均附明确许可

## 1. 词典数据

| 来源 | 文件 | 规模 | 许可 | 用途 |
|---|---|---|---|---|
| **CC-CEDICT** | `cedict.u8` | 125,427 条 | **CC BY-SA 4.0** | 中文词头、拼音、繁简、义项骨架 |
| **CFDICT**（Chine-Informations.com） | `cfdict.u8` | 60,438 条 | **CC BY-SA 3.0** | 中→法义项 |
| **Lexique 3.83** | `Lexique383.tsv` | 142,694 词形 | **CC BY-SA 4.0** | 法语词形、词性、**IPA 音标**、音节划分 |

### 引用要求

三份数据均为 CC BY-SA 系列，**转载或再发布需署名并以相同方式共享**。本项目的 `NOTICE.md` 与三语 README 均已列明出处；若修改或增补数据，衍生数据同样以 CC BY-SA 发布。

### 关键说明

- **音标不从零生成**。所有 IPA 来自 Lexique383 的 `phon` 字段，这是公开、通用、可复核的法语发音转写基准。模型不参与音标生成（红线 R5）。
- **CFDICT 许可已确认**（CC BY-SA 3.0，允许商业与非商业使用，需署名 + 相同方式共享），不是"待核"状态。
- 中文例句池复用了汉南辞典的汉文侧语料，见第 3 节。

## 2. 字体

| 字体 | 文件 | 许可 | 用途 |
|---|---|---|---|
| 霞鹜文楷 LXGW WenKai | `app/fonts/wenkai.woff2` | SIL OFL 1.1 | 汉字、标点 |
| **Gentium Plus** 或 **Noto Sans** | `app/fonts/ipa.woff2` | SIL OFL 1.1 | **IPA 专用**（ɥ ɲ ŋ ʁ ɡ ø œ ə 等） |

> 霞鹜文楷的拉丁部分对 IPA 覆盖不完整，`ʁ ɲ ŋ ɥ ɡ` 等字形很可能缺失。因此 IPA 单独用一套完整的 OFL 字体，通过 `unicode-range` 切分，不混排。

## 3. 例句语料

| 来源 | 规模 | 许可/说明 |
|---|---|---|
| 汉南辞典 `examples.json` 汉文侧 | 114,601 条 | 本项目自有语料，只复用汉文侧 |
| Index-Translate 翻译 | 法语侧 | 生成内容，模型 Apache-2.0 |

法语译文**全部**由 Index-Translate 免费公共网关产生，逐条可追溯到缓存行的 `request_id` 与时间戳（红线 R1/R4）。

## 4. 翻译模型

| 项目 | 值 |
|---|---|
| 端点 | `https://index-translate.bilibili.com/v1` |
| 模型 | `Index-Translate-35B-A3B` |
| 许可 | Apache-2.0 |
| 性质 | 免费公共网关（B 站开源项目） |

**本项目不调用任何其他翻译服务**：不用 DeepSeek、不用 OpenAI、不用 Google Translate、不用自建模型。管线脚本内含端点白名单，命中白名单外的域名直接拒绝启动。

## 5. 品牌资产

| 项目 | 来源 | 说明 |
|---|---|---|
| WuyuqIris 徽标 | [BewlyIris](https://github.com/SiqYin/BewlyIris) `brand/` | 本项目作者自绘；只取用 logo，不取用代码 |

BewlyIris 的 LICENSE 是 BewlyCat 自定义许可（MIT + 禁止封装成客户端）。该限制**针对代码**，品牌标识不受其约束；本项目仅取用 `brand/` 下的 logo 矢量与位图。

## 6. 代码

本项目代码以 **MIT** 发布。**词典数据不适用 MIT**，权利归原始数据提供方（CC BY-SA 系列）。

## 7. 引用格式

```
漢法辭典 (Dictionnaire chinois-français), 2026.
Chinese headwords and pinyin from CC-CEDICT (CC BY-SA 4.0).
Chinese–French glosses from CFDICT, Chine-Informations.com (CC BY-SA 3.0).
French IPA transcriptions from Lexique 3.83, New & Pallier (CC BY-SA 4.0).
Logo from WuyuqIris / BewlyIris (original artwork).
```
