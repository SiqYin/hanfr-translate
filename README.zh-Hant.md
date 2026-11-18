# 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[中文](README.md) · [Français](README.fr.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md)

漢語 ⇄ 法語雙向詞典。**每個法語詞都附 IPA 音標，例句標註聯誦。** 離線優先，同一套程式碼跑在網頁、Windows、Android 三端。

**[▶ 線上使用](https://siqyin.github.io/hanfr-translate-web/)**

---

## 它和一般漢法詞典不一樣的地方

查「水」，一般詞典給你 `eau`，到此為止。這裡給你的是：

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

例句  請喝杯水，潤潤嗓子。
      Veuillez boire un verre d'eau pour vous rafraîchir.
      /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

**音標不是擺設，是可以核對的。** 全部來自 Lexique 3.83——法國 CNRS 維護的公開法語詞庫，覆蓋 14.2 萬詞形。不是模型猜的。

查不到音標的詞標「待核」，不猜。這個決定有依據：我們實測過規則推算法語音標的準確率只有 **50.4%**，用它填充等於一半是錯的。

---

## 功能

### 查詞

- 中文（簡體或繁體）→ 法語實際用詞 + 拼音 + 繁簡對照 + **IPA 音標** + 詞性
- 法語 → 對應中文。**可省略變音符號**：`cafe` 查得到 `café`，`francais` 查得到 `français`
- 四語介面：简体中文 / 繁體中文 / Français / English
- 查詞記錄、翻譯記錄

### 音標直接查詢

輸入法語詞或整句，直接出音標：

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

整句音標帶聯誦，覆蓋 12.5 萬詞形，連詞典沒收錄的專業詞（`butène`、`chrysène`）也查得到。

### 變體字母兼容

按國際法語詞典通行做法，`œ ⇄ oe`、`æ ⇄ ae`、去變音符、大小寫全部等價：

| 輸入 | 結果 |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

### 例句與聯誦

每個詞條都有例句：中文 + 法語 + 法語整句音標。**聯誦直接標在音標上**，用 U+203F（undertie ‿）：

```
法語  Ceci est‿un livre.
音標  /səsi ɛst‿œ̃ livʁ/
```

三類聯誦分色標註：

| 類型 | 符號 | 例 |
|---|---|---|
| 必須 obligatoire | `‿` 綠色 | `les‿amis` /le.z‿ami/ |
| 可選 facultative | `‿` 黃色虛線 | `des‿étudiants` |
| 禁止 interdite | `\|` 紅色 | `les \| héros`（h aspiré） |

判定用確定性規則引擎（`app/liaison.js`），不是統計模型，**61 項測試全過**。

### AI 翻譯

- 中 → 法 / 法 → 中雙向
- 只用 [Index-Translate](https://github.com/bilibili/Index-Translate) 免費公共介面
- 譯文逐詞可點，懸停即查

---

## 音標體系說明

法語的鼻化元音有兩套標法，本專案採用**按真實發音**的一套：

| 傳統標法（20 世紀初定型） | 本專案標法 | 例 |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

理由：傳統標法反映的是約一個世紀前的發音。實際巴黎法語裡 /ɛ̃/ 與 /œ̃/ 已經合併，/ɑ̃/ 讀的不是後低元音 /ɑ/，/ɔ̃/ 的音值更接近 o。

需要傳統標法的讀者，可以按上表反向對照。

---

## 資料規模

| 項目 | 數量 |
|---|---:|
| 中文詞條 | 58,358 |
| 詞條帶例句 | 58,193（99.7%） |
| 例句總數 | 285,152 |
| 聯誦標註 | 208,569 處 |
| 法→中反查條目 | 49,463 |
| 音標詞形 | 125,868 |
| 功能詞人工定稿 | 311 |

---

## 下載

| 平台 | 檔案 | 說明 |
|---|---|---|
| 網頁 | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | 免安裝 |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | 安裝版，約 87 MB |
| Android | [HanFrDict-1.0.0-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-1.0.0-android.apk) | 直接安裝，需 Android 6.0+ |

Windows 包未做程式碼簽名，首次執行 SmartScreen 會提示「更多資訊 → 仍要執行」。
Android 用正式簽名（SHA256 `FA:94:29:4E…C4:7A:06`），後續版本可直接覆蓋升級。

---

## 技術架構

| 層 | 做法 |
|---|---|
| 前端 | 純 HTML/CSS/JS，無框架、無建置步驟 |
| 詞庫 | 單檔 JS，58,358 條，28 MB |
| 音標 | Lexique 3.83 的音素編碼經反推映射轉 IPA（36 個編碼，多詞例交叉驗證） |
| 聯誦 | 確定性規則引擎，61 項測試 |
| 分詞 | 中文後向最大匹配；法語詞典最長匹配（1–4 詞） |
| 翻譯 | Index-Translate OpenAI 相容介面，端點白名單硬編碼 |
| 字體 | 霞鶩文楷（漢字）+ Gentium Plus（IPA，含 U+203F 聯誦符） |
| 桌面 | Electron 33 + electron-builder（NSIS） |
| Android | 原生 WebView 殼 + Gradle 8.7 |
| 網頁 | GitHub Pages，Actions 部署 |

### 為什麼音標不靠 AI 生成

`tools/eval_g2p.py` 在 3000 條抽樣上跑規則式音標生成，精確匹配率 **50.4%**。用它填充剩餘詞條 = 一半音標是錯的。所以音標只取 Lexique 實測值，缺失標「待核」。

### 為什麼聯誦必須三分

判錯比不標更糟——學習者會照著錯的讀。規則來自法語的語法範疇（限定詞+名詞、代詞+動詞、h aspiré 之後、et 之後……），不是統計。

---

## 資料來源與授權

| 來源 | 用途 | 授權 |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | 中文詞頭、拼音 | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | 中→法義項 | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | 法語 IPA、詞性 | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | 繁簡轉換 | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | 翻譯模型 | Apache-2.0 |

三份詞典資料均為 CC BY-SA：**轉載或再發布需署名並以相同方式共享**。
程式碼以 MIT 發布，資料不適用 MIT。

Logo 取自作者另一專案 [BewlyIris](https://github.com/SiqYin/BewlyIris) 的 `brand/` 目錄（原創自繪）。

---

## 本地開發

```bash
npm install

# 網頁預覽
python tools/serve.py 5200
# http://localhost:5200/?q=水

# 重建詞庫（需要 02_数据管线/原始数据 中的資料）
python tools/build_zhfr.py
python tools/build_ipa_dict.py

# 測試
node tools/test_liaison.js     # 聯誦 61 項
node tools/test_ipa_query.js   # 音標查詢 35 項
node tools/check_i18n.js       # 四語言鍵位
python tools/qa_check.py       # 品質檢查清單

# 打包
npx electron-builder --win nsis --config.directories.output=release-out
```

Android 建置：

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> 注意：AGP 不允許專案路徑含非 ASCII 字元。若路徑有中文，請在純 ASCII 目錄建置。

---

## 已知限制

1. **音標缺口約 8.3%**：Lexique 未收錄的專業詞、派生詞，標「待核」而非猜。
2. **例句法語未經母語者審校**：Index-Translate 生成，品質好但未逐條人工核。
3. **部分 facultative 聯誦的判斷存在學理分歧**：按主流教學語法處理，UI 用虛線標識「可選」。
4. **整句音標不含語調**：只給音段轉寫，不標 intonation。
5. **`plus` 等多音詞未按句法消歧**：取 Lexique 預設讀音。
6. **詞庫規模受資料源限制**：CFDICT 只有 6 萬條，大於它的中法開源詞典目前沒有。

---

## 致謝

- [漢南辭典](https://github.com/SiqYin/zhongviet-translate) —— 本專案的流程與架構來源
- [BewlyIris](https://github.com/SiqYin/BewlyIris) —— Logo
- Lexique 3.83（New, Pallier et al., CNRS）
- CFDICT（Chine-Informations.com, David Houstin）
- CC-CEDICT
