# Chinese–French Dictionary 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[中文](README.md) · [Français](README.fr.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md)

A bidirectional Chinese ⇄ French dictionary. **Every French word carries its IPA transcription, and examples are annotated for liaison.** Offline-first; one codebase runs on web, Windows and Android.

**[▶ Use online](https://siqyin.github.io/hanfr-translate-web/)**

---

## What makes it different

Look up 水 (water) in an ordinary dictionary and you get `eau`, full stop. Here you get:

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

Example  请喝杯水，润润嗓子。
         Veuillez boire un verre d'eau pour vous rafraîchir.
         /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

**The transcription is not decoration — it is verifiable.** Every transcription comes from Lexique 3.83, the contemporary French lexical database maintained by CNRS, covering 142,000 word forms. None is model-generated.

Where a transcription cannot be found, the entry says "to be verified" instead of guessing. That decision rests on a measurement: our rule-based transcriber reaches only **50.4%** accuracy. Using it to fill gaps would publish one error in two.

---

## Features

### Lookup

- Chinese (simplified or traditional) → actual French word + pinyin + simplified/traditional pairing + **IPA** + part of speech
- French → Chinese equivalent. **Diacritics are optional**: `cafe` finds `café`, `francais` finds `français`
- Four interface languages: 简体中文 / 繁體中文 / Français / English
- Search history and translation history

### Direct transcription

Type a French word or a whole sentence and get the transcription:

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

Sentences include liaison marking. 125,868 forms covered, including technical terms the dictionary itself does not list (`butène`, `chrysène`).

### Orthographic variants

Following standard French lexicographic practice, `œ ⇄ oe`, `æ ⇄ ae`, diacritic stripping and case are all equivalent:

| Input | Result |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

### Examples and liaison

Every entry has an example: Chinese + French + full-sentence transcription. **Liaisons are marked inside the transcription itself**, using U+203F (undertie ‿):

```
French  Ceci est‿un livre.
IPA     /səsi ɛst‿œ̃ livʁ/
```

Three liaison types, colour-coded:

| Type | Symbol | Example |
|---|---|---|
| obligatoire (required) | `‿` green | `les‿amis` /le.z‿ami/ |
| facultative (optional) | `‿` dashed yellow | `des‿étudiants` |
| interdite (forbidden) | `\|` red | `les \| héros` (h aspiré) |

The engine is deterministic (`app/liaison.js`), driven by grammatical categories rather than statistics. **61 tests, all passing.**

### AI translation

- Chinese → French and French → Chinese
- Uses only the free public [Index-Translate](https://github.com/bilibili/Index-Translate) API
- Every translated word is clickable

---

## Transcription convention

French has two conventions for nasal vowels. This project follows **actual pronunciation**:

| Traditional (early 20th c.) | This project | Example |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

Reason: the traditional convention describes pronunciation as it was a century ago. In present-day Parisian French /ɛ̃/ and /œ̃/ have merged, /ɑ̃/ is no longer the back low vowel /ɑ/, and /ɔ̃/ is closer to o.

The table above lets readers convert back to the traditional convention where needed.

---

## Data volume

| Item | Count |
|---|---:|
| Chinese entries | 58,358 |
| Entries with example | 58,193 (99.7%) |
| Examples in total | 285,152 |
| Liaisons annotated | 208,569 |
| French → Chinese entries | 49,463 |
| Forms transcribed | 125,868 |
| Function words hand-revised | 311 |

---

## Download

| Platform | File | Note |
|---|---|---|
| Web | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | Nothing to install |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | Installer, ~87 MB |
| Android | [HanFrDict-1.0.0-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-1.0.0-android.apk) | Android 6.0+ |

The Windows build is unsigned, so SmartScreen will warn: "More info" → "Run anyway".
The APK uses a production signature (SHA256 `FA:94:29:4E…C4:7A:06`), so later versions install over it.

---

## Architecture

| Layer | Approach |
|---|---|
| Front end | Plain HTML/CSS/JS, no framework, no build step |
| Lexicon | Single JS file, 58,358 entries, 28 MB |
| IPA | Lexique 3.83 phonemic codes converted to IPA (36 codes, cross-checked across words) |
| Liaison | Deterministic rule engine, 61 tests |
| Segmentation | Chinese: backward maximum matching; French: longest match (1–4 words) |
| Translation | Index-Translate, OpenAI-compatible, hard-coded endpoint allow-list |
| Fonts | LXGW WenKai (hanzi) + Gentium Plus (IPA, includes U+203F) |
| Desktop | Electron 33 + electron-builder (NSIS) |
| Android | Native WebView shell + Gradle 8.7 |
| Web | GitHub Pages via Actions |

### Why the transcription is not AI-generated

`tools/eval_g2p.py` scores a rule-based transcriber on 3,000 samples: **50.4%** exact match. Filling gaps with it would publish one error in two. Transcriptions therefore come only from Lexique; gaps are marked "to be verified".

### Why liaison needs three categories

A mis-marked liaison is worse than none: the learner will read the mistake. The rules derive from grammatical categories (determiner + noun, pronoun + verb, after h aspiré, after et…), not from statistics.

---

## Sources and licences

| Source | Use | Licence |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | Chinese headwords, pinyin | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | Chinese → French glosses | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | French IPA, part of speech | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Simplified / traditional conversion | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | Translation model | Apache-2.0 |

All three lexical datasets are CC BY-SA: **redistribution requires attribution and share-alike**.
The code is MIT; the data is not.

The logo comes from the author's other project [BewlyIris](https://github.com/SiqYin/BewlyIris), directory `brand/` (original artwork).

---

## Local development

```bash
npm install

# Web preview
python tools/serve.py 5200
# http://localhost:5200/?q=水

# Rebuild the lexicon
python tools/build_zhfr.py
python tools/build_ipa_dict.py

# Tests
node tools/test_liaison.js     # liaison, 61 cases
node tools/test_ipa_query.js   # transcription, 35 cases
node tools/check_i18n.js       # four-language key alignment
python tools/qa_check.py       # quality checklist

# Packaging
npx electron-builder --win nsis --config.directories.output=release-out
```

Android build:

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> AGP rejects project paths containing non-ASCII characters. If the path has Chinese text, build from an ASCII-only directory.

---

## Known limitations

1. **About 8.3% of transcriptions missing**: technical terms and derivatives absent from Lexique, marked "to be verified".
2. **French examples not reviewed by a native speaker**: generated by Index-Translate, good quality but not checked one by one.
3. **Some facultative liaisons are debated**: handled per mainstream school grammar, flagged with a dashed style.
4. **No intonation**: segmental transcription only.
5. **`plus` and similar double-pronunciation words**: default Lexique reading, without syntactic disambiguation.
6. **Size limited by source**: CFDICT has only 60,000 entries; no larger free Chinese–French dictionary currently exists.

---

## Credits

- [漢南辭典](https://github.com/SiqYin/zhongviet-translate) — the architecture and method this project descends from
- [BewlyIris](https://github.com/SiqYin/BewlyIris) — logo
- Lexique 3.83 (New, Pallier et al., CNRS)
- CFDICT (Chine-Informations.com, David Houstin)
- CC-CEDICT
