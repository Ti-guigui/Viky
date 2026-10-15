"""Apprentissage de la voix : vous lisez des phrases, Viky retient comment elle vous entend.

Lancé par apprendre_ma_voix.bat (python -m viky --apprendre). Les corrections sont
enregistrées dans Documents/Viky/prononciation.json et appliquées automatiquement.
On peut le relancer quand on veut : les nouvelles corrections s'ajoutent aux anciennes.
"""

from __future__ import annotations

import queue
import time

# Des phrases de commande riches en R, en « ch », « j » et en mots propres à Viky.
PHRASES = [
    "Viky",
    "Viky, quelle heure est-il ?",
    "Rappelle-moi d'appeler Paul à dix-huit heures trente",
    "Projette la présentation du mariage",
    "Diapo suivante",
    "Reviens à la diapo précédente",
    "Va à la diapo trois",
    "Écran noir",
    "Rallume l'écran",
    "Remplace bonjour par bonsoir",
    "Quel temps fait-il demain ?",
    "Fais-moi le point",
    "Lis mes mails",
    "Envoie un mail à Marie",
    "Qu'est-ce que j'ai de prévu cette semaine ?",
    "Mets la musique en pause",
    "Chanson suivante",
    "Monte le son",
    "Ouvre le navigateur",
    "Verrouille l'ordinateur",
    "Mode spectacle",
    "Révèle la carte",
    "Quelle est sa carte ?",
    "Raconte-moi une blague",
    "Enregistre le fichier",
]


def record_phrase(stream_queue: queue.Queue, segmenter, timeout: float = 8.0) -> bytes | None:
    """Attend une phrase au micro (jusqu'au silence qui suit)."""
    import numpy as np

    segmenter.reset()
    while not stream_queue.empty():
        stream_queue.get_nowait()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            block = stream_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        segment = segmenter.feed(block, np.frombuffer(block, dtype=np.int16))
        if segment:
            return segment
    return None


def run(recognizer, pronunciation, lang: str = "fr", rounds: int = 2) -> int:
    """Fait lire chaque phrase `rounds` fois. Renvoie le nombre de corrections apprises."""
    import sounddevice as sd

    from .audio import BLOCK_SIZE, SAMPLE_RATE, Segmenter

    print("\n=== Apprentissage de votre voix ===")
    print("Lisez chaque phrase à voix haute, naturellement, comme vous parlerez à Viky.")
    print("Appuyez sur Entrée pour commencer chaque phrase (ou tapez « s » pour passer, « q » pour finir).\n")
    blocks: queue.Queue = queue.Queue()
    segmenter = Segmenter()
    learned_total = 0

    def on_audio(indata, frames, time_info, status) -> None:
        blocks.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="int16", channels=1,
                           callback=on_audio):
        time.sleep(1)  # le micro mesure le bruit ambiant
        for number, phrase in enumerate(PHRASES, start=1):
            for attempt in range(rounds):
                answer = input(f"[{number}/{len(PHRASES)}] « {phrase} »  (Entrée puis parlez) ").strip().lower()
                if answer == "q":
                    pronunciation.save()
                    return learned_total
                if answer == "s":
                    break
                print("   … je vous écoute")
                audio = record_phrase(blocks, segmenter)
                if audio is None:
                    print("   Je n'ai rien entendu. Rapprochez-vous du micro.")
                    continue
                heard = recognizer.transcribe(audio)
                text = heard.get(lang) or next(iter(heard.values()), "")
                learned = pronunciation.learn(phrase, text)
                learned_total += len(learned)
                if learned:
                    fixes = ", ".join(f"« {bad} » → « {good} »" for bad, good in learned)
                    print(f"   Entendu : « {text} »  — j'apprends : {fixes}")
                else:
                    print(f"   Entendu : « {text} »  — parfait !")
        pronunciation.save()
    return learned_total
