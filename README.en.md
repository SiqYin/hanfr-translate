# Chinese–French Dictionary 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[繁體中文](README.md) · [Français](README.fr.md) · [English](README.en.md)

A bidirectional Chinese ⇄ French dictionary. Every French word carries its IPA transcription, and examples are annotated for liaison. Offline-first; one codebase runs on web, Windows and Android.

**[▶ Use online](https://siqyin.github.io/hanfr-translate-web/)**

---

## Lookup

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

Example  请喝杯水，润润嗓子。
         Veuillez boire un verre d'eau pour vous rafraîchir.
         /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

- Chinese (simplified or traditional) → French word + pinyin + simplified/traditional pairing + IPA + part of speech
- French → Chinese equivalent. Diacritics are optional: `cafe` finds `café`, `francais` finds `français`
- Four interface languages: 繁體中文 / 简体中文 / Français / English
- Search history and translation history

## Direct transcription

Type a word or a whole sentence and get the transcription:

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

125,868 forms covered, including technical terms such as `butène` and `chrysène`.

## Orthographic variants

`œ ⇄ oe`, `æ ⇄ ae`, diacritic stripping and case are all equivalent:

| Input | Result |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

## Examples and liaison

Every entry has an example: Chinese + French + full-sentence transcription. Liaisons are marked inside the transcription itself, using U+203F (undertie ‿):

```
French  Ceci est‿un livre.
IPA     /səsi ɛst‿œ̃ livʁ/
```

Three liaison types, colour-coded:

| Type | Symbol | Example |
|---|---|---|
| obligatoire (required) | `‿` green | `les‿amis` |
| facultative (optional) | `‿` dashed yellow | `des‿étudiants` |
| interdite (forbidden) | `\|` red | `les \| héros` (h aspiré) |

Every French word in an example is clickable.

## AI translation

- Chinese → French and French → Chinese
- Free public [Index-Translate](https://github.com/bilibili/Index-Translate) API
- Every translated word is clickable

## Interface

- Colours: Chinese in red, French in blue, each with four tones
- Material You style: large radii, per-section tinted surfaces, soft shadows, floating top bar
- Three themes: light / dark / system
- Four interface languages

## Transcription convention

Nasal vowels follow actual pronunciation:

| Traditional | This project | Example |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

The table above lets readers convert back to the traditional convention.

## Data volume

| Item | Count |
|---|---:|
| Chinese entries | 58,358 |
| Entries with example | 58,239 (99.8%) |
| Forms transcribed | 125,868 |
| French → Chinese entries | 49,463 |
| Liaisons annotated | 78,782 |

## Download

| Platform | File | Note |
|---|---|---|
| Web | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | Nothing to install |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | Installer |
| Android | [HanFrDict-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-android.apk) | Android 6.0+ |

All three links always point to the latest version.

The Windows build is unsigned, so SmartScreen will warn.
The APK uses the same production signing key, so later versions install over it.

## Architecture

| Layer | Approach |
|---|---|
| Front end | Plain HTML/CSS/JS, no framework, no build step |
| Lexicon | Single JS file, 58,358 entries |
| IPA | Lexique 3.83 phonemic codes converted to IPA |
| Liaison | Deterministic rule engine, 61 tests |
| Segmentation | Chinese: backward maximum matching; French: longest match (1–4 words) |
| Translation | Index-Translate, OpenAI-compatible |
| Fonts | LXGW WenKai (hanzi) + Gentium Plus (IPA, includes U+203F) |
| Desktop | Electron 33 + electron-builder (NSIS) |
| Android | Native WebView shell + Gradle 8.7 |
| Web | GitHub Pages via Actions |

## Sources and licences

| Source | Use | Licence |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | Chinese headwords, pinyin | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | Chinese → French glosses | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | French IPA, part of speech | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Simplified / traditional conversion | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | Translation model | Apache-2.0 |

All three lexical datasets are CC BY-SA: redistribution requires attribution and share-alike.
The code is MIT; the data is not.

The logo comes from the author's other project [BewlyIris](https://github.com/SiqYin/BewlyIris), directory `brand/` (original artwork).

## Local development

```bash
npm install

python tools/serve.py 5200

python tools/build_zhfr.py
python tools/build_ipa_dict.py

node tools/test_liaison.js     # liaison, 61 cases
node tools/test_ipa_query.js   # transcription, 35 cases
node tools/check_i18n.js       # four-language key alignment
python tools/qa_check.py       # quality checklist

npx electron-builder --win nsis --config.directories.output=release-out
```

Android build:

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> AGP rejects project paths containing non-ASCII characters.

## Known limitations

1. About 8.3% of transcriptions missing: technical terms and derivatives absent from Lexique, marked "to be verified".
2. Translations not reviewed by a native speaker.
3. Some facultative liaisons are debated; handled per mainstream school grammar.
4. No intonation: segmental transcription only.
5. `plus` and similar double-pronunciation words: default Lexique reading.

## Credits

- [BewlyIris](https://github.com/SiqYin/BewlyIris) — logo
- Lexique 3.83 (New, Pallier et al., CNRS)
- CFDICT (Chine-Informations.com, David Houstin)
- CC-CEDICT
