# Viky 🎙️

**Viky** est une assistante vocale pour ordinateur. Elle fonctionne **entièrement hors ligne** : votre voix ne quitte jamais votre machine. Elle comprend le **français** (en priorité) et l'**anglais**.

> Plateforme principale : **Windows 10 / 11**. Linux et macOS sont prévus ; les fonctions de base y marchent déjà en partie.

## Ce que Viky sait faire

Réveillez Viky en disant **« Viky »** ou en **tapant deux fois dans vos mains**, puis donnez votre commande. Vous pouvez aussi tout dire d'un coup : *« Viky, ouvre Chrome »*.

| Exemple en français | Exemple en anglais | Action |
|---|---|---|
| « Ouvre Google Chrome » | "Open Google Chrome" | Ouvre une application |
| « Ouvre YouTube », « Va sur lemonde point fr » | "Go to github.com" | Ouvre un site |
| « Ouvre mes téléchargements » | "Open my downloads" | Ouvre un dossier |
| « Ouvre la caméra » | "Open the camera" | Lance l'application Caméra |
| « Ferme Chrome » | "Close Spotify" | Ferme une application |
| « Cherche la recette des crêpes » | "Search for the weather" | Recherche Google |
| « Mets Aya Nakamura sur YouTube » | "Play lofi on YouTube" | Recherche YouTube |
| « Quelle heure est-il ? », « On est quel jour ? » | "What time is it?" | Heure et date |
| « Monte le son », « Baisse le son », « Coupe le son » | "Volume up", "Mute" | Volume |
| « Prends une photo », « Fais une capture d'écran » | "Take a picture" | Enregistre dans *Images\Viky* |
| « Note que je dois appeler maman » | "Take a note that…" | Ajoute à *Documents\Viky\notes.txt* |
| « Verrouille l'ordinateur » | "Lock the computer" | Verrouille la session |
| « Raconte-moi une blague » | "Tell me a joke" | 😄 |
| « Parle en anglais » / « Parle en français » | "Speak French" | Change la langue de réponse |
| « Qu'est-ce que tu sais faire ? » | "What can you do?" | Aide |
| « Au revoir » | "Goodbye" | Arrête Viky |

Viky répond dans la langue de votre commande. Les applications sont trouvées automatiquement dans le menu Démarrer : « ouvre Spotify » ou « ouvre Discord » fonctionnent sans réglage.

## Installation sur Windows

1. Installez **Python 3.11 ou plus récent** depuis [python.org](https://www.python.org/downloads/). Pendant l'installation, cochez **« Add python.exe to PATH »**.
2. Téléchargez Viky : bouton vert **Code → Download ZIP** sur GitHub, puis décompressez le dossier.
3. Double-cliquez sur **`installer.bat`**. Le script installe les dépendances et télécharge les modèles de reconnaissance vocale (environ 90 Mo, une seule fois).
4. Double-cliquez sur **`lancer_viky.bat`**. Dites « Viky ! »

### Avoir une voix française

Viky utilise les voix intégrées à Windows. Si elle parle français avec un accent anglais, installez la voix française :
**Paramètres → Heure et langue → Voix → Ajouter des voix → Français (France)**.

## Utilisation avancée

```bat
lancer_viky.bat --texte      :: taper les commandes au clavier (pratique pour tester)
lancer_viky.bat --muet       :: afficher les réponses sans les prononcer
lancer_viky.bat --langue en  :: répondre en anglais par défaut
```

### Personnaliser Viky

Ouvrez **`config.toml`** avec le Bloc-notes. Vous pouvez :

- ajouter vos propres applications et sites (section `[applications]` et `[sites]`) ;
- désactiver le double clap ou régler sa sensibilité ;
- n'écouter qu'en français (`langues_ecoute = ["fr"]`) pour économiser de la mémoire.

**Viky ne réagit pas à son nom ?** La fenêtre affiche ce qu'elle entend (`Entendu : …`). Si elle comprend par exemple « nicky » au lieu de « Viky », ajoutez `"nicky"` à `mots_de_reveil` dans `config.toml`.

## Linux et macOS (expérimental)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m viky --telecharger-modeles
python -m viky
```

Sous Linux, installez aussi `espeak-ng` (voix) et `portaudio` (micro), par exemple `sudo apt install espeak-ng libportaudio2`.

## Comment ça marche

| Fichier | Rôle |
|---|---|
| `viky/audio.py` | Découpe le son du micro en phrases et détecte le double clap |
| `viky/recognizer.py` | Transcrit la voix en texte avec [Vosk](https://alphacephei.com/vosk/), hors ligne |
| `viky/intents.py` | Comprend la commande (français et anglais) |
| `viky/assistant.py` | Gère le réveil et exécute les commandes |
| `viky/actions.py` | Agit sur l'ordinateur (applications, volume, photos…) |
| `viky/speaker.py` | Fait parler Viky avec les voix du système |
| `viky/messages.py` | Toutes les phrases de Viky, dans les deux langues |

Pour ajouter une commande : une règle dans `intents.py`, sa réponse dans `messages.py`, son action dans `assistant.py`.

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Feuille de route

- [ ] Rappels et minuteur
- [ ] Météo hors ligne / sans clé
- [ ] Contrôle de la musique (pause, suivant)
- [ ] Icône dans la barre des tâches et démarrage avec Windows
- [ ] Prise en charge complète de Linux et macOS
- [ ] Exécutable Windows `.exe` sans installation de Python

## Licence

[MIT](LICENSE)
