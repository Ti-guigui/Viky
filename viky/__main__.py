"""Point d'entrée : python -m viky"""

from __future__ import annotations

import argparse
import queue
import sys
from pathlib import Path

from .assistant import Assistant
from .config import MODELS_DIR, load_config
from .speaker import Speaker


def run_text(assistant: Assistant) -> None:
    assistant.greet(text_mode=True)
    langs = assistant.config.listen_langs
    while True:
        try:
            line = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if line and not assistant.on_utterance({lang: line for lang in langs}, require_wake=False):
            return


def _drain(q: queue.Queue) -> None:
    while not q.empty():
        q.get_nowait()


def run_voice(assistant: Assistant) -> None:
    import numpy as np
    import sounddevice as sd

    from .audio import BLOCK_SECONDS, BLOCK_SIZE, SAMPLE_RATE, ClapDetector, Segmenter
    from .recognizer import ModelMissing, Recognizer

    config = assistant.config
    try:
        recognizer = Recognizer(config.listen_langs, MODELS_DIR)
    except ModelMissing:
        print("Aucun modèle de reconnaissance vocale trouvé.\n"
              "Lancez d'abord : python -m viky --telecharger-modeles")
        sys.exit(1)

    blocks: queue.Queue[bytes] = queue.Queue()
    segmenter = Segmenter()
    claps = ClapDetector(config.clap_sensitivity) if config.double_clap else None
    elapsed = 0.0

    def on_audio(indata, frames, time_info, status) -> None:
        blocks.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="int16",
                           channels=1, callback=on_audio):
        assistant.greet()
        _drain(blocks)
        print("(Ctrl+C pour quitter)")
        while True:
            block = blocks.get()
            elapsed += BLOCK_SECONDS
            samples = np.frombuffer(block, dtype=np.int16)
            heard = None
            if claps and claps.feed(samples, elapsed):
                assistant.wake()
            else:
                segment = segmenter.feed(block, samples)
                if segment is None:
                    continue
                heard = recognizer.transcribe(segment)
                if any(heard.values()):
                    print("Entendu :", " | ".join(f"{k}: {v}" for k, v in heard.items() if v))
                if not assistant.on_utterance(heard):
                    return
            # Oublie ce que le micro a capté pendant que Viky parlait.
            _drain(blocks)
            segmenter.reset()


def start_remote(assistant: Assistant) -> None:
    from .remote import Remote, new_pin

    config = assistant.config
    remote = Remote(assistant.remote_action, config.remote_pin or new_pin(), config.remote_port)
    try:
        remote.start()
    except OSError as error:
        print(f"[Viky] Télécommande indisponible ({error}).")
        return
    print(f"[Viky] Télécommande : ouvrez {remote.url} sur votre téléphone (même Wi-Fi). Code : {remote.pin}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="viky", description="Viky, assistante vocale hors ligne.")
    parser.add_argument("--texte", action="store_true", help="taper les commandes au clavier au lieu de parler")
    parser.add_argument("--muet", action="store_true", help="afficher les réponses sans les prononcer")
    parser.add_argument("--langue", choices=["fr", "en"], help="langue de réponse par défaut")
    parser.add_argument("--config", type=Path, help="chemin d'un autre fichier config.toml")
    parser.add_argument("--telecharger-modeles", action="store_true",
                        help="télécharger les modèles de reconnaissance vocale puis quitter")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.langue:
        config.lang = args.langue
        if args.langue not in config.listen_langs:
            config.listen_langs.insert(0, args.langue)

    if args.telecharger_modeles:
        from .models import download_all

        download_all(config.listen_langs, MODELS_DIR)
        return

    assistant = Assistant(config, Speaker(config.voice_rate, mute=args.muet))
    assistant.reminders.start()
    if config.remote:
        start_remote(assistant)
    try:
        run_text(assistant) if args.texte else run_voice(assistant)
    except KeyboardInterrupt:
        print()
        assistant.tell("bye")


if __name__ == "__main__":
    main()
