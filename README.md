# 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[中文](README.md) · [Français](README.fr.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md)

汉语 ⇄ 法语双向词典。**每个法语词都附 IPA 音标，例句标注联诵。** 离线优先，同一套代码跑在网页、Windows、Android 三端。

**[▶ 在线使用](https://siqyin.github.io/hanfr-translate-web/)**

---

## 它和一般汉法词典不一样的地方

查「水」，一般词典给你 `eau`，到此为止。这里给你的是：

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

例句  请喝杯水，润润嗓子。
      Veuillez boire un verre d'eau pour vous rafraîchir.
      /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

**音标不是摆设，是可以核对的。** 全部来自 Lexique 3.83——法国 CNRS 维护的公开法语词库，覆盖 14.2 万词形。不是模型猜的。

查不到音标的词标「待核」，不猜。这个决定有依据：我们实测过规则推算法语音标的准确率只有 **50.4%**，用它填充等于一半是错的。

---

## 功能

### 查词

- 中文（简体或繁体）→ 法语实际用词 + 拼音 + 繁简对照 + **IPA 音标** + 词性
- 法语 → 对应中文。**可省略变音符号**：`cafe` 查得到 `café`，`francais` 查得到 `français`
- 四语界面：简体中文 / 繁體中文 / Français / English
- 查词记录、翻译记录

### 音标直接查询

输入法语词或整句，直接出音标：

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

整句音标带联诵，覆盖率 12.5 万词形，连词典没收录的专业词（`butène`、`chrysène`）也查得到。

### 变体字母兼容

按国际法语词典通行做法，`œ ⇄ oe`、`æ ⇄ ae`、去变音符、大小写全部等价：

| 输入 | 结果 |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

### 例句与联诵

每个词条都有例句：中文 + 法语 + 法语整句音标。**联诵直接标在音标上**，用 U+203F（undertie ‿）：

```
法語  Ceci est‿un livre.
音標  /səsi ɛst‿œ̃ livʁ/
```

三类联诵分色标注：

| 类型 | 符号 | 例 |
|---|---|---|
| 必须 obligatoire | `‿` 绿色 | `les‿amis` /le.z‿ami/ |
| 可选 facultative | `‿` 黄色虚线 | `des‿étudiants` |
| 禁止 interdite | `\|` 红色 | `les \| héros`（h aspiré） |

判定用确定性规则引擎（`app/liaison.js`），不是统计模型，**61 项测试全过**。

### AI 翻译

- 中 → 法 / 法 → 中双向
- 只用 [Index-Translate](https://github.com/bilibili/Index-Translate) 免费公共接口
- 译文逐词可点，悬停即查

---

## 音标体系说明

法语的鼻化元音有两套标法，本项目采用**按真实发音**的一套：

| 传统标法（20 世纪初定型） | 本项目标法 | 例 |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

理由：传统标法反映的是约一个世纪前的发音。实际巴黎法语里 /ɛ̃/ 与 /œ̃/ 已经合并，/ɑ̃/ 读的不是后低元音 /ɑ/，/ɔ̃/ 的音值更接近 o。

需要传统标法的读者，可以按上表反向对照。

---

## 数据规模

| 项目 | 数量 |
|---|---:|
| 中文词条 | 58,358 |
| 词条带例句 | 58,193（99.7%） |
| 例句总数 | 285,152 |
| 联诵标注 | 208,569 处 |
| 法→中反查条目 | 49,463 |
| 音标词形 | 125,868 |
| 功能词人工定稿 | 311 |

---

## 下载

| 平台 | 文件 | 说明 |
|---|---|---|
| 网页 | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | 免安装 |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | 安装版，约 87 MB |
| Android | [HanFrDict-1.0.0-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-1.0.0-android.apk) | 直接安装，需 Android 6.0+ |

Windows 包未做代码签名，首次运行 SmartScreen 会提示「更多信息 → 仍要运行」。
Android 用正式签名（SHA256 `FA:94:29:4E…C4:7A:06`），后续版本可直接覆盖升级。

---

## 技术架构

| 层 | 做法 |
|---|---|
| 前端 | 纯 HTML/CSS/JS，无框架、无构建步骤 |
| 词库 | 单文件 JS，58,358 条，28 MB |
| 音标 | Lexique 3.83 的音素编码经反推映射转 IPA（36 个编码，多词例交叉验证） |
| 联诵 | 确定性规则引擎，61 项测试 |
| 分词 | 中文后向最大匹配；法语词典最长匹配（1–4 词） |
| 翻译 | Index-Translate OpenAI 兼容接口，端点白名单硬编码 |
| 字体 | 霞鹜文楷（汉字）+ Gentium Plus（IPA，含 U+203F 联诵符） |
| 桌面 | Electron 33 + electron-builder（NSIS） |
| Android | 原生 WebView 壳 + Gradle 8.7 |
| 网页 | GitHub Pages，Actions 部署 |

### 为什么音标不靠 AI 生成

`tools/eval_g2p.py` 在 3000 条抽样上跑规则式音标生成，精确匹配率 **50.4%**。用它填充剩余词条 = 一半音标是错的。所以音标只取 Lexique 实测值，缺失标「待核」。

### 为什么联诵必须三分

判错比不标更糟——学习者会照着错的读。规则来自法语的语法范畴（限定词+名词、代词+动词、h aspiré 之后、et 之后……），不是统计。

---

## 数据来源与授权

| 来源 | 用途 | 授权 |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | 中文词头、拼音 | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | 中→法义项 | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | 法语 IPA、词性 | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | 繁简转换 | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | 翻译模型 | Apache-2.0 |

三份词典数据均为 CC BY-SA：**转载或再发布需署名并以相同方式共享**。
代码以 MIT 发布，数据不适用 MIT。

Logo 取自作者另一项目 [BewlyIris](https://github.com/SiqYin/BewlyIris) 的 `brand/` 目录（原创自绘）。

---

## 本地开发

```bash
npm install

# 网页预览
python tools/serve.py 5200
# http://localhost:5200/?q=水

# 重建词库（需要 02_数据管线/原始数据 中的数据）
python tools/build_zhfr.py
python tools/build_ipa_dict.py

# 测试
node tools/test_liaison.js     # 联诵 61 项
node tools/test_ipa_query.js   # 音标查询 35 项
node tools/check_i18n.js       # 四语言键位
python tools/qa_check.py       # 质量检查清单

# 打包
npx electron-builder --win nsis --config.directories.output=release-out
```

Android 构建：

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> 注意：AGP 不允许项目路径含非 ASCII 字符。若路径有中文，请在纯 ASCII 目录构建。

---

## 已知限制

1. **音标缺口约 8.3%**：Lexique 未收录的专业词、派生词，标「待核」而非猜。
2. **例句法语未经母语者审校**：Index-Translate 生成，质量好但未逐条人工核。
3. **部分 facultative 联诵的判断存在学理分歧**：按主流教学语法处理，UI 用虚线标识「可选」。
4. **整句音标不含语调**：只给音段转写，不标 intonation。
5. **`plus` 等多音词未按句法消歧**：取 Lexique 默认读音。
6. **词库规模受数据源限制**：CFDICT 只有 6 万条，大于它的中法开源词典目前没有。

---

## 致谢

- [汉南辞典](https://github.com/SiqYin/zhongviet-translate) —— 本项目的流程与架构来源
- [BewlyIris](https://github.com/SiqYin/BewlyIris) —— Logo
- Lexique 3.83（New, Pallier et al., CNRS）
- CFDICT（Chine-Informations.com, David Houstin）
- CC-CEDICT
