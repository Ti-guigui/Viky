"""Un seul fil graphique (Tkinter) partagé par toutes les fenêtres de Viky.

Tkinter n'accepte d'être piloté que depuis le fil qui l'a créé : les autres fils
(micro, télécommande, rappels) déposent leurs demandes dans une file d'attente.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

_shared: "TkLoop | None" = None


class TkLoop:
    def __init__(self) -> None:
        self.tasks: queue.Queue = queue.Queue()
        self.ready = threading.Event()
        self.failed = False
        self.root = None
        self.tk = None
        threading.Thread(target=self._run, daemon=True, name="interface").start()
        self.ready.wait(timeout=10)

    def _run(self) -> None:
        try:
            import tkinter as tk

            self.root = tk.Tk()
        except Exception as error:  # pas d'écran ou tkinter non installé
            print(f"[Viky] Interface graphique indisponible ({error}). Réinstallez Python en cochant "
                  "« tcl/tk and IDLE ».")
            self.failed = True
            self.ready.set()
            return
        self.tk = tk
        self.root.withdraw()
        self.ready.set()
        self._poll()
        self.root.mainloop()

    def _poll(self) -> None:
        try:
            while True:
                function, args = self.tasks.get_nowait()
                try:
                    function(*args)
                except Exception:
                    import traceback

                    traceback.print_exc()
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    def call(self, function: Callable, *args) -> None:
        """Exécute `function(*args)` dans le fil graphique (depuis n'importe quel fil)."""
        if not self.failed:
            self.tasks.put((function, args))


def shared_loop() -> TkLoop:
    global _shared
    if _shared is None:
        _shared = TkLoop()
    return _shared
