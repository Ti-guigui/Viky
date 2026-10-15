# Viky 🎙️✨

**Viky** est une assistante vocale pour ordinateur, pensée pour les **présentations** et les **spectacles de magie**. Elle comprend le **français** en priorité, ainsi que l'**anglais**.

- La reconnaissance de la voix se fait **hors ligne**, sur votre PC.
- Elle pilote vos **PDF, PowerPoint et Excel** et les envoie sur le **rétroprojecteur** à la voix.
- Elle donne la **météo** et les **grands titres**, répond à vos **questions** et fait des **recherches complètes** avec l'IA.
- Elle a un **mode spectacle** : mots-codes secrets, révélations animées sur le projecteur et télécommande cachée sur votre téléphone.

> Plateforme principale : **Windows 10 / 11** avec Microsoft Office. Linux et macOS sont prévus plus tard.

---

## 1. Parler à Viky

Dites **« Viky »**, ou tapez **deux fois dans vos mains**, puis votre commande. Vous pouvez aussi tout dire d'un coup : *« Viky, projette la présentation mariage »*.

### Fichiers et projecteur

Branchez le projecteur en **HDMI**, en mode **écran étendu** (touche Windows + P → Étendre). Viky trouve vos fichiers dans le Bureau, les Documents, les Téléchargements, les Images et les Vidéos (OneDrive compris), ainsi que dans les dossiers que vous ajoutez.

| Vous dites | Viky fait |
|---|---|
| « Ouvre le tableau budget » | Ouvre `Budget 2026.xlsx` sur votre écran |
| « Projette la présentation mariage » | Lance le diaporama **sur le projecteur** |
| « Mets le PDF contrat sur le projecteur » | Ouvre le PDF et le déplace sur le projecteur |
| « Envoie ça sur le grand écran » | Déplace la fenêtre ouverte sur le projecteur |
| « Ouvre la dernière présentation » | Ouvre la présentation la plus récente |
| « Suivant », « Reviens en arrière », « Va à la diapo cinq » | Fait défiler diapos, pages ou photos |
| « Écran noir », « Rallume l'écran » | Met le projecteur au noir, puis rallume l'image |
| « Lance le diaporama », « Arrête la présentation » | Démarre ou arrête le diaporama |
| « Mets en plein écran », « Ferme le fichier » | Plein écran, fermeture |
| « Duplique l'écran », « Étends l'écran », « Projecteur seulement » | Change le mode d'affichage |

### Modifier à la voix

| Vous dites | Viky fait |
|---|---|
| « Mets 500 dans la cellule B3 » | Écrit 500 dans B3 (Excel ouvert) |
| « La cellule C 12 vaut douze virgule cinq » | Écrit 12,5 dans C12 |
| « Écris payé dans la case D4 » | Écrit le texte « payé » |
| « Lis la cellule B3 », « Efface la cellule B3 » | Lit ou vide la cellule |
| « Feuille suivante » | Passe à l'onglet suivant |
| « Change le titre de la diapo en Bienvenue » | Modifie le titre de la diapo affichée |
| « Enregistre » | Enregistre le fichier Excel ou PowerPoint |

### Météo, actualité et intelligence

| Vous dites | Viky fait |
|---|---|
| « Quel temps fait-il ? », « La météo à Lyon demain » | Météo de l'endroit où vous êtes, ou de la ville demandée |
| « Les grands titres » | Lit les 5 titres de France Info (ou du Monde) |
| « Approfondis le numéro deux » | Lit l'article et vous l'explique |
| « Pourquoi le ciel est bleu ? », « Qui était Houdini ? » | Répond avec l'IA |
| « Approfondis », « Et pourquoi ? » | Développe sa dernière réponse |
| « Fais-moi une recherche complète sur les illusionnistes » | Recherche sur le web, résumé oral et rapport détaillé |
| « Affiche le rapport », « Projette le rapport » | Ouvre le rapport, sur le PC ou sur le projecteur |

### Et aussi

Ouvrir des applications et des sites (« Ouvre Chrome », « Va sur YouTube »), chercher sur Google ou YouTube, l'heure et la date, le volume, une photo ou une capture d'écran, des notes (« Note que… »), verrouiller le PC, des blagues, et changer de langue (« Parle en anglais »).

---

## 2. Le mode spectacle 🎩

Dites **« Viky, mode spectacle »**, ou appuyez sur **Spectacle** dans la télécommande. Dans ce mode :

- Viky **ne dit jamais « je n'ai pas compris »** devant le public. Elle se tait.
- Les **mots-codes** deviennent actifs : une phrase anodine déclenche un effet **sans dire « Viky »**.
- Les **répliques préparées** sont actives : vous dites « Viky, es-tu prête ? » et elle répond exactement le texte que vous avez écrit.
- Quand elle répond avec l'IA, Viky adopte une **personnalité de scène** : mystérieuse, drôle et brève, et elle ne révèle jamais un secret.

### La télécommande secrète (téléphone)

Au démarrage, Viky affiche une ligne comme :

```
[Viky] Télécommande : ouvrez http://192.168.1.23:8765 sur votre téléphone (même Wi-Fi). Code : 4821
```

Ouvrez cette adresse sur votre téléphone, entrez le code, puis ajoutez la page à l'écran d'accueil. Elle est sombre et s'appelle « Notes » pour rester discrète. Elle sert à :

- **charger le secret** : la carte choisie par le spectateur (en deux touches, par exemple 7 puis ♥) ou un mot ;
- **Révéler** : la carte se retourne sur le projecteur, ou le mot apparaît en fondu doré ;
- **Deviner** : Viky fait le numéro de voyance (« Je me concentre… Je vois… le sept de cœur ! »), puis la révélation s'affiche ;
- **Dire / Afficher** : faire parler Viky, ou écrire un texte sur le projecteur ;
- passer les diapos, mettre l'**écran au noir** ou l'effacer.

> La première fois, Windows demande d'autoriser Python sur le réseau : cliquez sur **Autoriser** (réseau privé).

### Exemple de numéro

1. Un spectateur choisit une carte et la montre au public. Vous la voyez discrètement.
2. Dans votre poche, sur le téléphone, vous touchez **7** puis **♥**.
3. Vous dites : *« Viky, quelle est sa carte ? »*
4. Viky : *« Je me concentre… Je perçois une image… Je vois… le sept de cœur ! »*, et le 7 ♥ se retourne en grand sur le projecteur.

Variante sans téléphone : le mot-code *« regardez bien l'écran »* révèle le secret en silence.

### Préparer vos mots-codes et répliques

Dans `config.toml`, section `[magie]` :

```toml
[[magie.codes]]
phrase = "regardez bien l'écran"   # la phrase que vous direz naturellement
effet = "reveler"                   # reveler, deviner, noir, effacer, dire, afficher,
                                    # charger, projeter, suivant, precedent
[[magie.codes]]
phrase = "pensez très fort"
effet = "charger"
valeur = "dame de pique"            # charge un secret convenu à l'avance

[magie.repliques]
"es-tu prête" = "Toujours. Je suis née prête."
```

Testez chaque phrase en répétition : la fenêtre affiche ce que Viky a compris (`Entendu : …`). Choisissez des phrases de 3 ou 4 mots que vous ne dites pas par hasard.

---

## 3. Installation sur Windows

1. Installez **Python 3.11 ou plus récent** depuis [python.org](https://www.python.org/downloads/). Cochez **« Add python.exe to PATH »**.
2. Téléchargez Viky (**Code → Download ZIP** sur GitHub) et décompressez le dossier.
3. Double-cliquez sur **`installer.bat`**. Le script installe les dépendances et les modèles de reconnaissance vocale (environ 90 Mo, une seule fois).
4. Double-cliquez sur **`lancer_viky.bat`**.

**Lancer Viky à chaque démarrage de Windows** : double-cliquez sur **`demarrage_auto.bat`**. Viky démarre alors toute seule, en fenêtre réduite. Pour annuler : `retirer_demarrage_auto.bat`.

**Voix française** : si Viky a un accent anglais, allez dans **Paramètres → Heure et langue → Voix → Ajouter des voix → Français**.

### L'intelligence artificielle (optionnel, mais recommandé)

Viky fonctionne sans IA, mais les questions, les recherches et l'explication des actualités en ont besoin. Vous pouvez installer l'une des deux, ou les deux :

- **IA locale, gratuite et privée** : installez [Ollama](https://ollama.com), puis dans un terminal : `ollama pull qwen2.5:7b`. Il faut 16 Go de RAM. Avec 8 Go, utilisez `qwen2.5:3b` et changez `modele_local` dans `config.toml`.
- **Claude**, pour les recherches complètes sur le web : créez une clé sur [console.anthropic.com](https://console.anthropic.com), puis collez-la dans `config.toml` (`cle_claude = "sk-ant-…"`). C'est payant à l'usage : une question coûte une fraction de centime, une recherche complète quelques centimes.

Viky utilise l'IA locale pour les questions courantes, et Claude pour les recherches et l'actualité. Si l'une des deux manque, elle se sert de l'autre.

### Lancer en mode texte (pour tester sans micro)

```bat
lancer_viky.bat --texte
```

---

## 4. Réglages (`config.toml`)

Ouvrez `config.toml` avec le Bloc-notes. Vous pouvez y régler :

- `[general]` : la langue, les variantes du prénom « Viky », le double clap ;
- `[fichiers]` : vos dossiers (par exemple celui de vos spectacles) ;
- `[projecteur]` : la vue présentateur (vos notes sur le PC, les diapos sur le projecteur) ;
- `[meteo]` : votre ville (sinon, détection automatique) ;
- `[actualites]` : le nombre de titres et les flux RSS ;
- `[ia]` : le modèle local et la clé Claude ;
- `[magie]` : les mots-codes, les répliques et le code PIN de la télécommande ;
- `[applications]` et `[sites]` : vos raccourcis.

**Viky ne réagit pas à son nom ?** Regardez ce qu'elle a entendu (`Entendu : …`) et ajoutez ce mot à `mots_de_reveil`.

---

## 5. Comment c'est fait

| Fichier | Rôle |
|---|---|
| `viky/audio.py`, `recognizer.py` | Micro, découpage des phrases, double clap, reconnaissance vocale [Vosk](https://alphacephei.com/vosk/) |
| `viky/intents.py` | Comprend les commandes (français et anglais) |
| `viky/assistant.py` | Le cerveau : réveil, commandes, mode spectacle |
| `viky/files.py` | Retrouve un fichier à partir de son nom prononcé |
| `viky/projector.py` | 2e écran, PowerPoint et Excel (Windows) |
| `viky/weather.py`, `news.py` | Météo (Open-Meteo) et actualités (RSS) |
| `viky/brain.py`, `report.py` | IA locale (Ollama), Claude, rapports de recherche |
| `viky/magic.py`, `stage.py`, `remote.py` | Secrets, mots-codes, écran de révélation, télécommande |
| `viky/speaker.py`, `messages.py` | Voix de Viky et toutes ses phrases |

Tests : `pip install -r requirements-dev.txt` puis `python -m pytest`.

## Feuille de route

- [ ] Rappels et minuteur
- [ ] Envoyer un fichier par e-mail à la voix
- [ ] Modifications Excel/PowerPoint plus libres grâce à l'IA (« ajoute une ligne total »)
- [ ] Plus d'effets de révélation (nombre, dessin, prédiction cachée dans un fichier)
- [ ] Icône dans la barre des tâches et démarrage avec Windows
- [ ] Exécutable Windows `.exe` sans installation de Python
- [ ] Prise en charge complète de Linux et macOS

## Licence

[MIT](LICENSE)
