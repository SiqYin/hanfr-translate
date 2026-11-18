# Dictionnaire chinois-français 漢法辭典

<p align="center"><img src="docs/logo.png" width="200" alt="漢法辭典"></p>

[中文](README.md) · [Français](README.fr.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md)

Dictionnaire bidirectionnel chinois ⇄ français. **Chaque mot français est accompagné de sa transcription API, et les exemples sont annotés pour les liaisons.** Fonctionne hors ligne, même code sur le web, Windows et Android.

**[▶ Utiliser en ligne](https://siqyin.github.io/hanfr-translate-web/)**

---

## Ce qui le distingue d'un dictionnaire ordinaire

Pour « 水 » (eau), un dictionnaire courant vous donne `eau`, et c'est tout. Ici :

```
水  shuǐ
1  eau      /o/      n.f.
2  liquide  /likid/  n.m.

Exemple  请喝杯水，润润嗓子。
         Veuillez boire un verre d'eau pour vous rafraîchir.
         /vœje bwaʁ œ̃ vɛʁ do puʁ vu ʁafʁɛʃiʁ/
```

**La transcription n'est pas décorative : elle est vérifiable.** Toutes proviennent de Lexique 3.83, la base lexicale du français contemporain maintenue par le CNRS, qui couvre 142 000 formes. Aucune n'est inventée par un modèle.

Lorsqu'une transcription est introuvable, le dictionnaire affiche « à vérifier » plutôt que de deviner. Ce choix est fondé sur une mesure : notre générateur de transcription par règles n'atteint que **50,4 %** d'exactitude. L'utiliser pour combler les lacunes reviendrait à publier une erreur sur deux.

---

## Fonctionnalités

### Recherche

- Chinois (simplifié ou traditionnel) → mot français réel + pinyin + correspondance simplifié/traditionnel + **API** + catégorie grammaticale
- Français → équivalent chinois. **Les diacritiques sont facultatifs** : `cafe` trouve `café`, `francais` trouve `français`
- Interface en quatre langues : 简体中文 / 繁體中文 / Français / English
- Historique des recherches et des traductions

### Transcription directe

Saisissez un mot ou une phrase entière, obtenez la transcription :

```
maison  →  /mɛzõ/

Nous sommes allés au parc hier après-midi.
→  /nu sɔmz‿alez‿o paʁk | jɛʁ apʁɛmidi./
```

Les phrases incluent les liaisons. 125 868 formes couvertes, y compris des termes techniques absents du dictionnaire (`butène`, `chrysène`).

### Variantes orthographiques

Conformément à l'usage des grands dictionnaires français, `œ ⇄ oe`, `æ ⇄ ae`, la suppression des diacritiques et la casse sont toutes équivalentes :

| Saisie | Résultat |
|---|---|
| `cœur` / `coeur` | `/kœʁ/` |
| `eleve` / `élève` | `/ɛləv/` |
| `francais` / `français` | `/fʁɑ̃sɛ/` |
| `hotel` / `hôtel` | `/ɔtɛl/` |
| `PARIS` | `/paʁi/` |

### Exemples et liaisons

Chaque entrée a son exemple : chinois + français + transcription de la phrase. **Les liaisons sont marquées directement dans la transcription**, avec U+203F (undertie ‿) :

```
Français  Ceci est‿un livre.
API       /səsi ɛst‿œ̃ livʁ/
```

Trois types de liaisons, distingués par couleur :

| Type | Symbole | Exemple |
|---|---|---|
| obligatoire | `‿` vert | `les‿amis` /le.z‿ami/ |
| facultative | `‿` pointillé jaune | `des‿étudiants` |
| interdite | `\|` rouge | `les \| héros` (h aspiré) |

Le moteur est déterministe (`app/liaison.js`), fondé sur les catégories grammaticales — pas sur un modèle statistique. **61 tests, tous verts.**

### Traduction IA

- Chinois → français et français → chinois
- Uniquement l'API publique gratuite [Index-Translate](https://github.com/bilibili/Index-Translate)
- Chaque mot de la traduction est cliquable

---

## Convention de transcription

Le français connaît deux conventions pour les voyelles nasales. Ce projet suit **la prononciation réelle** :

| Convention traditionnelle (début XXᵉ) | Ce projet | Exemple |
|---|---|---|
| /ɛ̃/ | **/ã/** | `pain` /pã/ |
| /œ̃/ | **/ã/** | `brun` /bʁã/ |
| /ɑ̃/ | **/ɒ̃/** | `temps` /tɒ̃/ |
| /ɔ̃/ | **/õ/** | `bon` /bõ/ |

Raison : la convention traditionnelle décrit une prononciation vieille d'un siècle. En français parisien actuel, /ɛ̃/ et /œ̃/ ont fusionné, /ɑ̃/ ne se prononce plus comme la voyelle postérieure /ɑ/, et la valeur de /ɔ̃/ est plus proche de o.

Le tableau ci-dessus permet de revenir à la convention traditionnelle si nécessaire.

---

## Volume des données

| Élément | Nombre |
|---|---:|
| Entrées chinoises | 58 358 |
| Entrées avec exemple | 58 193 (99,7 %) |
| Exemples au total | 285 152 |
| Liaisons annotées | 208 569 |
| Entrées français → chinois | 49 463 |
| Formes transcrites | 125 868 |
| Mots grammaticaux révisés à la main | 311 |

---

## Téléchargement

| Plateforme | Fichier | Remarque |
|---|---|---|
| Web | [siqyin.github.io/hanfr-translate-web](https://siqyin.github.io/hanfr-translate-web/) | Sans installation |
| Windows | [HanFrDict-setup.exe](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-setup.exe) | Installateur, ~87 Mo |
| Android | [HanFrDict-1.0.0-android.apk](https://github.com/SiqYin/hanfr-translate/releases/latest/download/HanFrDict-1.0.0-android.apk) | Android 6.0+ |

Le paquet Windows n'est pas signé : SmartScreen affichera un avertissement (« Informations complémentaires » → « Exécuter quand même »).
L'APK utilise une signature de production (SHA256 `FA:94:29:4E…C4:7A:06`), les mises à jour ultérieures s'installent par-dessus.

---

## Architecture

| Couche | Approche |
|---|---|
| Front-end | HTML/CSS/JS pur, sans framework ni étape de build |
| Lexique | Fichier JS unique, 58 358 entrées, 28 Mo |
| API | Codes phonémiques de Lexique 3.83 convertis en API (36 codes, recoupés sur plusieurs mots) |
| Liaisons | Moteur déterministe, 61 tests |
| Segmentation | Chinois : plus longue correspondance arrière ; français : plus longue correspondance (1–4 mots) |
| Traduction | Index-Translate, compatible OpenAI, liste blanche d'endpoints codée en dur |
| Polices | LXGW WenKai (sinogrammes) + Gentium Plus (API, contient U+203F) |
| Bureau | Electron 33 + electron-builder (NSIS) |
| Android | WebView natif + Gradle 8.7 |
| Web | GitHub Pages via Actions |

### Pourquoi la transcription n'est pas générée par IA

`tools/eval_g2p.py` évalue un générateur par règles sur 3 000 échantillons : **50,4 %** d'exactitude. L'utiliser reviendrait à publier une erreur sur deux. Les transcriptions viennent donc uniquement de Lexique ; les lacunes affichent « à vérifier ».

### Pourquoi les liaisons sont classées en trois types

Une liaison mal marquée est pire qu'une absence de marque : l'apprenant lira la faute. Les règles découlent des catégories grammaticales (déterminant + nom, pronom + verbe, après h aspiré, après et…), pas de statistiques.

---

## Sources et licences

| Source | Usage | Licence |
|---|---|---|
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | Entrées chinoises, pinyin | CC BY-SA 4.0 |
| [CFDICT](http://www.chine-informations.com/chinois/open/CFDICT/) | Gloses chinois → français | CC BY-SA 3.0 |
| [Lexique 3.83](http://www.lexique.org/) | API, catégories | CC BY-SA 4.0 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Simplifié / traditionnel | Apache-2.0 |
| [Index-Translate](https://github.com/bilibili/Index-Translate) | Modèle de traduction | Apache-2.0 |

Les trois jeux de données sont sous CC BY-SA : **toute rediffusion exige l'attribution et le partage à l'identique**.
Le code est sous MIT ; les données ne le sont pas.

Le logo provient du projet [BewlyIris](https://github.com/SiqYin/BewlyIris), répertoire `brand/` (création originale de l'auteur).

---

## Développement local

```bash
npm install

# Aperçu web
python tools/serve.py 5200
# http://localhost:5200/?q=水

# Reconstruire le lexique
python tools/build_zhfr.py
python tools/build_ipa_dict.py

# Tests
node tools/test_liaison.js     # liaisons, 61 cas
node tools/test_ipa_query.js   # transcription, 35 cas
node tools/check_i18n.js       # alignement des quatre langues
python tools/qa_check.py       # liste de contrôle qualité

# Empaquetage
npx electron-builder --win nsis --config.directories.output=release-out
```

Build Android :

```bash
cd android
JAVA_HOME=<jdk17> ./gradlew assembleRelease
```

> AGP refuse les chemins contenant des caractères non ASCII. Si le chemin comporte des idéogrammes, compilez depuis un répertoire ASCII.

---

## Limites connues

1. **8,3 % de transcriptions manquantes** : termes techniques et dérivés absents de Lexique, marqués « à vérifier ».
2. **Traductions non relues par un locuteur natif** : générées par Index-Translate, de bonne qualité mais non vérifiées une à une.
3. **Certaines liaisons facultatives font débat** : traitement selon la grammaire scolaire dominante, signalé en pointillé.
4. **Pas d'intonation** : transcription segmentale seulement.
5. **`plus` et autres mots à double prononciation** : lecture par défaut de Lexique, sans désambiguïsation syntaxique.
6. **Taille limitée par la source** : CFDICT ne compte que 60 000 entrées ; aucun dictionnaire chinois-français libre plus vaste n'existe à ce jour.

---

## Remerciements

- [漢南辭典](https://github.com/SiqYin/zhongviet-translate) — l'architecture et la méthode dont ce projet est issu
- [BewlyIris](https://github.com/SiqYin/BewlyIris) — logo
- Lexique 3.83 (New, Pallier et al., CNRS)
- CFDICT (Chine-Informations.com, David Houstin)
- CC-CEDICT
