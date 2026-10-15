"""L'écran de scène : une fenêtre plein écran sur le projecteur pour les révélations.

Effets : écran noir, texte qui apparaît en fondu ou lettre par lettre, et carte
à jouer qui se retourne. Sans projecteur (répétition), la fenêtre s'ouvre en
petit sur l'écran du PC.

Tkinter n'aime pas être piloté depuis plusieurs fils : la fenêtre vit dans son
propre fil et reçoit ses ordres par une file d'attente.
"""

from __future__ import annotations

from typing import Callable

from .magic import Card

BACKGROUND = "#000000"
GOLD = "#ffd76a"
CARD_RED = "#c8102e"
CARD_BLACK = "#111111"


def _blend(color: str, factor: float) -> str:
    """Mélange une couleur avec le noir : factor 0 = noir, 1 = couleur pleine."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def _rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius, x2, y2 - radius,
              x2, y2, x2 - radius, y2, x1 + radius, y2, x1, y2, x1, y2 - radius,
              x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class Stage:
    def __init__(self, screen_rect: Callable[[], tuple[int, int, int, int] | None], loop=None) -> None:
        """`screen_rect` renvoie la zone du projecteur (gauche, haut, droite, bas) ou None."""
        self.screen_rect = screen_rect
        self.loop = loop
        self.visible = False
        self.root = None

    # ------------------------------------------------------------ ordres (tous fils)

    def black(self) -> None:
        self._send("black")

    def show_text(self, text: str, style: str = "fondu") -> None:
        self._send("text", text, style)

    def show_card(self, card: Card, lang: str = "fr") -> None:
        self._send("card", card, lang)

    def hide(self) -> None:
        self._send("hide")

    def _send(self, command: str, *args) -> None:
        if self.loop is None:
            from .tkloop import shared_loop

            self.loop = shared_loop()
        self.loop.call(self._dispatch, command, args)

    # ------------------------------------------------------------ fil graphique

    def _dispatch(self, command: str, args: tuple) -> None:
        if self.root is None:
            tk = self.loop.tk
            self.tk = tk
            self.root = tk.Toplevel(self.loop.root)
            self.root.title("Viky — scène")
            self.root.configure(bg=BACKGROUND)
            self.root.withdraw()
            self.canvas = tk.Canvas(self.root, bg=BACKGROUND, highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self.root.bind("<Escape>", lambda event: self._hide())
            self._animation = 0
        getattr(self, f"_{command}")(*args)

    def _show(self) -> tuple[int, int]:
        rect = self.screen_rect()
        self.root.deiconify()
        if rect:
            left, top, right, bottom = rect
            self.root.overrideredirect(True)
            self.root.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
            self.root.attributes("-topmost", True)
        else:  # répétition sans projecteur : petite fenêtre sur le PC
            self.root.overrideredirect(False)
            self.root.geometry("960x540+80+80")
        self.root.update_idletasks()
        self.visible = True
        self._animation += 1  # interrompt l'animation précédente
        self.canvas.delete("all")
        width = self.root.winfo_width() if self.root.winfo_width() > 1 else 960
        height = self.root.winfo_height() if self.root.winfo_height() > 1 else 540
        return width, height

    def _hide(self) -> None:
        self._animation += 1
        self.canvas.delete("all")
        self.root.withdraw()
        self.visible = False

    def _black(self) -> None:
        self._show()

    def _text(self, text: str, style: str) -> None:
        width, height = self._show()
        size = max(24, int(height * (0.16 if len(text) < 20 else 0.09)))
        item = self.canvas.create_text(width / 2, height / 2, text="", fill=BACKGROUND,
                                       font=("Segoe UI", size, "bold"), width=width * 0.9,
                                       justify="center")
        animation = self._animation
        if style == "machine":  # lettre par lettre
            self.canvas.itemconfigure(item, fill=GOLD)

            def type_letter(count: int = 1) -> None:
                if animation != self._animation:
                    return
                self.canvas.itemconfigure(item, text=text[:count])
                if count < len(text):
                    self.root.after(90, type_letter, count + 1)
            type_letter()
        else:  # fondu depuis le noir
            self.canvas.itemconfigure(item, text=text)

            def fade(step: int = 0, steps: int = 50) -> None:
                if animation != self._animation:
                    return
                self.canvas.itemconfigure(item, fill=_blend(GOLD, step / steps))
                if step < steps:
                    self.root.after(40, fade, step + 1)
            fade()

    def _card(self, card: Card, lang: str) -> None:
        width, height = self._show()
        card_h = height * 0.72
        card_w = card_h * 0.7
        cx, cy = width / 2, height / 2
        animation = self._animation
        frames = 14

        def draw(scale: float, face: bool) -> None:
            self.canvas.delete("all")
            half = max(1.0, card_w * scale / 2)
            x1, y1, x2, y2 = cx - half, cy - card_h / 2, cx + half, cy + card_h / 2
            radius = card_w * 0.07 * scale
            if not face:
                _rounded_rect(self.canvas, x1, y1, x2, y2, radius, fill="#7a0f1f", outline="#f2f2f2", width=6)
                if scale > 0.15:
                    inset = card_w * 0.08 * scale
                    _rounded_rect(self.canvas, x1 + inset, y1 + card_w * 0.08, x2 - inset,
                                  y2 - card_w * 0.08, radius, outline=GOLD, width=3, fill="")
                    self.canvas.create_text(cx, cy, text="✦", fill=GOLD,
                                            font=("Segoe UI Symbol", int(card_h * 0.18 * scale) + 1))
                return
            color = CARD_RED if card.red else CARD_BLACK
            _rounded_rect(self.canvas, x1, y1, x2, y2, radius, fill="#fdfdfd", outline="#d9d9d9", width=4)
            if scale > 0.3:
                corner = f"{card.label(lang)}\n{card.suit}"
                font = ("Segoe UI", int(card_h * 0.075 * scale) + 1, "bold")
                self.canvas.create_text(x1 + card_w * 0.1 * scale, y1 + card_h * 0.04, text=corner,
                                        fill=color, font=font, anchor="n", justify="center")
                self.canvas.create_text(x2 - card_w * 0.1 * scale, y2 - card_h * 0.04, text=corner,
                                        fill=color, font=font, anchor="n", justify="center", angle=180)
            self.canvas.create_text(cx, cy, text=card.suit, fill=color,
                                    font=("Segoe UI Symbol", int(card_h * 0.4 * scale) + 1))

        def flip(frame: int = 0) -> None:
            if animation != self._animation:
                return
            if frame <= frames:  # le dos se referme
                draw(1 - frame / frames, face=False)
            else:  # la face s'ouvre
                draw((frame - frames) / frames, face=True)
            if frame < 2 * frames:
                self.root.after(30, flip, frame + 1)

        draw(1, face=False)
        self.root.after(900, flip)  # un instant de suspense sur le dos de la carte
