# Dictionnaire chinois-français 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[繁體中文](README.md) · [Français](README.fr.md) · [English](README.en.md)

Dictionnaire bidirectionnel chinois ⇄ français. Chaque mot français est accompagné de sa transcription API, et les exemples sont annotés pour les liaisons. Fonctionne hors ligne, même code sur le web, Windows et Android.

**[▶ Utiliser en ligne](https://siqyin.github.io/hanfr-translate-web/)**

---

## Recherche

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

Exemple  请喝杯水，润润嗓子。
         Veuillez boire un verre d'eau pour vous rafraîchir.
         /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

- Chinois (simplifié ou traditionnel) → mot français + pinyin + correspondance simplifié/traditionnel + API + catégorie grammaticale
- Français → équivalent chinois. Les diacritiques sont facultatifs : `cafe` trouve `café`, `francais` trouve `français`
- Interface en quatre langues : 繁體中文 / 简体中文 / Français / English
- Historique des recherches et des traductions

## Transcription directe

Saisissez un mot ou une phrase, obtenez la transcription :

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

125 868 formes couvertes, y compris des termes techniques comme `butène` ou `chrysène`.

## Variantes orthographiques

`œ ⇄ oe`, `æ ⇄ ae`, suppression des diacritiques et casse sont équivalentes :

| Saisie | Résultat |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

## Exemples et liaisons

Chaque entrée a son exemple : chinois + français + transcription de la phrase. Les liaisons sont marquées dans la transcription elle-même, avec U+203F (undertie ‿) :

```
Français  Ceci est‿un livre.
API       /səsi ɛst‿œ̃ livʁ/
```

Trois types de liaisons, distingués par couleur :

| Type | Symbole | Exemple |
|---|---|---|
| obligatoire | `‿` vert | `les‿amis` |
| facultative | `‿` pointillé jaune | `des‿étudiants` |
| interdite | `\|` rouge | `les \| héros` (h aspiré) |

Chaque mot français d'un exemple est cliquable.

## Traduction IA

- Chinois → français et français → chinois
- API publique gratuite [Index-Translate](https://github.com/bilibili/Index-Translate)
- Chaque mot de la traduction est cliquable

## Interface

- Couleurs : chinois en rouge, français en bleu, chacun décliné en quatre tons
- Style Material You : grands rayons, fonds colorés par section, ombres douces, barre supérieure flottante
- Trois thèmes : clair / sombre / système
- Quatre langues d'interface

## Convention de transcription

Les voyelles nasales suivent la prononciation réelle :

| Convention traditionnelle | Ce projet | Exemple |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

Le tableau ci-dessus permet de revenir à la convention traditionnelle.

## Volume des données

| Élément | Nombre |
|---|---:|
| Entrées chinoises | 58 358 |
| Entrées avec exemple | 58 239 (99,8 %) |
| Formes transcrites | 125 868 |
| Entrées français → chinois | 49 463 |
| Liaisons annotées | 78 782 |

## Téléchargement

| Plateforme | Fichier | Remarque |
|---|---|---|
| Web | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | Sans installation |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | Installateur |
| Android | [HanFrDict-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-android.apk) | Android 6.0+ |

Ces trois liens pointent toujours vers la dernière version.

Le paquet Windows n'est pas signé : SmartScreen affichera un avertissement.
L'APK utilise la même clé de signature de production ; les mises à jour s'installent par-dessus.

## Architecture

| Couche | Approche |
|---|---|
| Front-end | HTML/CSS/JS pur, sans framework ni étape de build |
| Lexique | Fichier JS unique, 58 358 entrées |
| API | Codes phonémiques de Lexique 3.83 convertis en API |
| Liaisons | Moteur déterministe, 61 tests |
| Segmentation | Chinois : plus longue correspondance arrière ; français : plus longue correspondance (1–4 mots) |
| Traduction | Index-Translate, compatible OpenAI |
| Polices | LXGW WenKai (sinogrammes) + Gentium Plus (API, contient U+203F) |
| Bureau | Electron 33 + electron-builder (NSIS) |
| Android | WebView natif + Gradle 8.7 |
| Web | GitHub Pages via Actions |

## Sources et licences

| Source | Usage | Licence |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | Entrées chinoises, pinyin | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | Gloses chinois → français | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | API, catégories | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Simplifié / traditionnel | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | Modèle de traduction | Apache-2.0 |

Les trois jeux de données sont sous CC BY-SA : toute rediffusion exige l'attribution et le partage à l'identique.
Le code est sous MIT ; les données ne le sont pas.

Le logo provient du projet [BewlyIris](https://github.com/SiqYin/BewlyIris), répertoire `brand/` (création originale de l'auteur).

## Développement local

```bash
npm install

python tools/serve.py 5200

python tools/build_zhfr.py
python tools/build_ipa_dict.py

node tools/test_liaison.js     # liaisons, 61 cas
node tools/test_ipa_query.js   # transcription, 35 cas
node tools/check_i18n.js       # alignement des quatre langues
python tools/qa_check.py       # liste de contrôle qualité

npx electron-builder --win nsis --config.directories.output=release-out
```

Build Android :

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> AGP refuse les chemins contenant des caractères non ASCII.

## Limites connues

1. 8,3 % de transcriptions manquantes : termes techniques et dérivés absents de Lexique, marqués « à vérifier ».
2. Traductions non relues par un locuteur natif.
3. Certaines liaisons facultatives font débat ; traitement selon la grammaire scolaire dominante.
4. Pas d'intonation : transcription segmentale seulement.
5. `plus` et autres mots à double prononciation : lecture par défaut de Lexique.

## Remerciements

- [BewlyIris](https://github.com/SiqYin/BewlyIris) — logo
- Lexique 3.83 (New, Pallier et al., CNRS)
- CFDICT (Chine-Informations.com, David Houstin)
- CC-CEDICT
