"""Interface façon Jarvis, dans une vraie fenêtre Windows (pas de navigateur).

- Widget : un petit réacteur animé dans un coin de l'écran, toujours visible.
  Double-clic : ouvre le HUD. Clic droit : menu.
- HUD : grand écran sombre et bleu néon avec le réacteur au centre, l'heure,
  la météo, les rappels, les grands titres, l'état du PC et la conversation.
  Une zone de saisie permet aussi de taper une commande.

Le réacteur change selon l'état de Viky : au repos (bleu), à l'écoute (bleu vif),
en réflexion (ambre), en train de parler (pulsation), mode spectacle (violet).
"""

from __future__ import annotations

import math
import random
import threading
import time
from datetime import datetime
from typing import Callable

BG = "#04070d"
CYAN = "#3fd8ff"
DIM = "#0e3442"
FAINT = "#0a1f29"
WHITE = "#e6f7ff"
GREY = "#7da3b3"
AMBER = "#ffb347"
PURPLE = "#b07cff"
GREEN = "#4dffa6"
KEY = "#010203"  # couleur rendue transparente autour du widget (Windows)

STATE_COLORS = {"idle": CYAN, "listening": "#8ff0ff", "thinking": AMBER, "speaking": CYAN, "stage": PURPLE}
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
          "octobre", "novembre", "décembre"]


class Reactor:
    """Le réacteur animé, dessiné sur un canevas Tkinter."""

    def __init__(self, canvas, cx: float, cy: float, radius: float) -> None:
        self.canvas = canvas
        self.cx, self.cy, self.radius = cx, cy, radius
        self.state = "idle"
        self.angle = 0.0
        self.level = 0.0  # « volume » simulé pendant que Viky parle
        r = radius
        self.items = {
            "glow": canvas.create_oval(0, 0, 0, 0, outline=FAINT, width=max(2, r * 0.18)),
            "ring": canvas.create_oval(0, 0, 0, 0, outline=DIM, width=max(1, r * 0.03)),
            "ticks": [canvas.create_line(0, 0, 0, 0, fill=DIM, width=max(1, r * 0.015)) for _ in range(48)],
            "arcs": [canvas.create_arc(0, 0, 0, 0, style="arc", outline=CYAN, width=max(2, r * 0.06))
                     for _ in range(3)],
            "inner": [canvas.create_arc(0, 0, 0, 0, style="arc", outline=CYAN, width=max(1, r * 0.03))
                      for _ in range(4)],
            "core": canvas.create_oval(0, 0, 0, 0, fill=CYAN, outline=""),
            "halo": canvas.create_oval(0, 0, 0, 0, outline=CYAN, width=max(1, r * 0.02)),
        }
        self._layout()

    def _box(self, r: float) -> tuple[float, float, float, float]:
        return self.cx - r, self.cy - r, self.cx + r, self.cy + r

    def _layout(self) -> None:
        c, r = self.canvas, self.radius
        c.coords(self.items["glow"], *self._box(r * 0.98))
        c.coords(self.items["ring"], *self._box(r * 0.88))
        for i, tick in enumerate(self.items["ticks"]):
            a = 2 * math.pi * i / len(self.items["ticks"])
            inner, outer = r * (0.78 if i % 4 else 0.74), r * 0.82
            c.coords(tick, self.cx + inner * math.cos(a), self.cy + inner * math.sin(a),
                     self.cx + outer * math.cos(a), self.cy + outer * math.sin(a))
        for arc in self.items["arcs"]:
            c.coords(arc, *self._box(r * 0.66))
        for arc in self.items["inner"]:
            c.coords(arc, *self._box(r * 0.45))

    def step(self) -> None:
        """Avance l'animation d'une image."""
        c, r = self.canvas, self.radius
        color = STATE_COLORS.get(self.state, CYAN)
        speed = {"idle": 0.6, "listening": 2.5, "thinking": 5.0, "speaking": 1.5, "stage": 1.0}.get(self.state, 0.6)
        self.angle = (self.angle + speed) % 360
        for i, arc in enumerate(self.items["arcs"]):
            c.itemconfigure(arc, start=self.angle + i * 120, extent=70, outline=color)
        for i, arc in enumerate(self.items["inner"]):
            c.itemconfigure(arc, start=-self.angle * 1.6 + i * 90, extent=40, outline=color)
        if self.state == "speaking":
            self.level = 0.6 * self.level + 0.4 * random.uniform(0.2, 1.0)
        else:
            self.level *= 0.85
        breathe = 0.5 + 0.5 * math.sin(time.monotonic() * (6 if self.state == "listening" else 2))
        core = r * (0.2 + 0.08 * self.level + 0.02 * breathe)
        c.coords(self.items["core"], *self._box(core))
        c.itemconfigure(self.items["core"], fill=color)
        c.coords(self.items["halo"], *self._box(core * (1.35 + 0.25 * self.level)))
        c.itemconfigure(self.items["halo"], outline=color)
        c.itemconfigure(self.items["ring"], outline=color if self.state != "idle" else DIM)


class JarvisUI:
    """Widget + HUD. Toutes les méthodes publiques peuvent être appelées depuis n'importe quel fil."""

    def __init__(self, loop, submit: Callable[[str], None], data: Callable[[], dict],
                 mode: str = "widget", on_quit: Callable[[], None] | None = None) -> None:
        """
        loop    : boucle graphique partagée (tkloop) ;
        submit  : appelée avec le texte tapé dans le HUD ;
        data    : data(lent) renvoie {"weather": str, "news": [str], "reminders": [str], "status": dict} ;
                  appelée dans un fil séparé ; « lent » vaut True quand il faut aussi rafraîchir
                  la météo et les titres (toutes les 30 minutes) ;
        """
        self.loop = loop
        self.submit = submit
        self.data = data
        self.on_quit = on_quit
        self.state = "idle"
        self.stage_mode = False
        self.lines: list[tuple[str, str]] = []  # (qui, texte)
        self.info: dict = {}
        self.hud = None
        self.widget = None
        self.loop.call(self._build, mode)
        threading.Thread(target=self._refresh_data, daemon=True, name="donnees-hud").start()

    # ------------------------------------------------------------ appels depuis Viky

    def on_event(self, event: str, value=None) -> None:
        """Branché sur assistant.listeners."""
        if event == "state":
            self.loop.call(self._set_state, value)
        elif event == "heard":
            self.loop.call(self._add_line, "vous", value)
        elif event == "reply":
            self.loop.call(self._add_line, "viky", value)
        elif event == "reminder":
            self.loop.call(self._add_line, "rappel", value)
        elif event == "stage":
            self.stage_mode = bool(value)
        elif event == "show_hud":
            self.loop.call(self._show_hud)
        elif event == "show_widget":
            self.loop.call(self._show_widget)

    # ------------------------------------------------------------ construction (fil graphique)

    def _build(self, mode: str) -> None:
        if mode == "hud":
            self._show_hud()
        else:
            self._show_widget()
        self._tick()

    def _make_widget(self) -> None:
        tk = self.loop.tk
        size = 150
        win = tk.Toplevel(self.loop.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=KEY)
        try:
            win.attributes("-transparentcolor", KEY)  # Windows : seul le réacteur est visible
        except tk.TclError:
            pass
        screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{size}x{size}+{screen_w - size - 24}+{screen_h - size - 72}")
        canvas = tk.Canvas(win, width=size, height=size, bg=KEY, highlightthickness=0)
        canvas.pack()
        self.widget_reactor = Reactor(canvas, size / 2, size / 2, size / 2 - 4)
        canvas.bind("<Double-Button-1>", lambda e: self._show_hud())
        canvas.bind("<ButtonPress-1>", self._drag_start)
        canvas.bind("<B1-Motion>", self._drag_move)
        menu = tk.Menu(win, tearoff=0)
        menu.add_command(label="Ouvrir le HUD", command=self._show_hud)
        menu.add_command(label="Quitter Viky", command=self._quit)
        canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.widget = win

    def _drag_start(self, event) -> None:
        self._drag = (event.x, event.y)

    def _drag_move(self, event) -> None:
        x = self.widget.winfo_x() + event.x - self._drag[0]
        y = self.widget.winfo_y() + event.y - self._drag[1]
        self.widget.geometry(f"+{x}+{y}")

    def _make_hud(self) -> None:
        tk = self.loop.tk
        win = tk.Toplevel(self.loop.root)
        win.title("Viky")
        win.configure(bg=BG)
        win.geometry("1280x720+40+40")
        try:
            win.state("zoomed")  # plein écran fenêtré sous Windows
        except tk.TclError:
            pass
        win.protocol("WM_DELETE_WINDOW", self._show_widget)
        win.bind("<Escape>", lambda e: self._show_widget())
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        entry = tk.Entry(win, bg="#071521", fg=WHITE, insertbackground=CYAN, relief="flat",
                         font=("Segoe UI", 14), highlightthickness=1, highlightcolor=CYAN,
                         highlightbackground=DIM)
        entry.place(relx=0.5, rely=0.955, anchor="center", relwidth=0.42, height=36)
        entry.insert(0, "Tapez une commande…")
        entry.bind("<FocusIn>", lambda e: entry.delete(0, "end") if entry.get().endswith("…") else None)
        entry.bind("<Return>", self._on_enter)
        self.hud, self.hud_canvas, self.entry = win, canvas, entry
        self.hud_reactor = None
        canvas.bind("<Configure>", lambda e: self._layout_hud())

    def _layout_hud(self) -> None:
        c = self.hud_canvas
        w, h = max(c.winfo_width(), 400), max(c.winfo_height(), 300)
        c.delete("all")
        # cadre et coins façon HUD
        m = 18
        for x1, y1, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            c.create_line(x1, y1, x1 + 60 * dx, y1, fill=CYAN, width=2)
            c.create_line(x1, y1, x1, y1 + 60 * dy, fill=CYAN, width=2)
        c.create_text(w / 2, 40, text="V I K Y", fill=CYAN, font=("Segoe UI", 20, "bold"))
        c.create_text(w / 2, 66, text="ASSISTANTE PERSONNELLE", fill=GREY, font=("Segoe UI", 9))
        radius = min(w, h) * 0.2
        self.hud_reactor = Reactor(c, w / 2, h * 0.42, radius)
        self.hud_items = {
            "clock": c.create_text(60, 70, text="", anchor="w", fill=WHITE, font=("Segoe UI Light", 44)),
            "date": c.create_text(64, 118, text="", anchor="w", fill=GREY, font=("Segoe UI", 13)),
            "weather": c.create_text(w - 60, 80, text="", anchor="e", fill=WHITE, font=("Segoe UI", 13),
                                     width=w * 0.3, justify="right"),
            "state": c.create_text(w / 2, h * 0.42 + radius + 30, text="", fill=CYAN, font=("Segoe UI", 12)),
        }
        panel_w = w * 0.25
        self.hud_items["reminders_title"] = c.create_text(60, h * 0.25, text="AGENDA ET RAPPELS", anchor="w",
                                                          fill=CYAN, font=("Segoe UI", 11, "bold"))
        self.hud_items["reminders"] = c.create_text(60, h * 0.25 + 24, text="", anchor="nw", fill=WHITE,
                                                    font=("Segoe UI", 11), width=panel_w)
        self.hud_items["news_title"] = c.create_text(w - 60 - panel_w, h * 0.25, text="ACTUALITÉS", anchor="w",
                                                     fill=CYAN, font=("Segoe UI", 11, "bold"))
        self.hud_items["news"] = c.create_text(w - 60 - panel_w, h * 0.25 + 24, text="", anchor="nw",
                                               fill=WHITE, font=("Segoe UI", 11), width=panel_w)
        self.hud_items["status"] = c.create_text(60, h * 0.78, text="", anchor="w", fill=GREY,
                                                 font=("Consolas", 11))
        self.hud_items["log"] = c.create_text(w / 2, h * 0.84, text="", fill=WHITE, font=("Segoe UI", 13),
                                              width=w * 0.6, justify="center")
        self._render_info()
        self._render_log()

    # ------------------------------------------------------------ affichage

    def _show_hud(self) -> None:
        if self.hud is None:
            self._make_hud()
        self.hud.deiconify()
        self.hud.lift()
        if self.widget is not None:
            self.widget.withdraw()

    def _show_widget(self) -> None:
        if self.widget is None:
            self._make_widget()
        self.widget.deiconify()
        if self.hud is not None:
            self.hud.withdraw()

    def _set_state(self, state: str) -> None:
        self.state = state

    def _add_line(self, who: str, text: str) -> None:
        if text:
            self.lines = (self.lines + [(who, text)])[-4:]
            self._render_log()

    def _render_log(self) -> None:
        if self.hud is None or not hasattr(self, "hud_items"):
            return
        prefix = {"vous": "Vous : ", "viky": "Viky : ", "rappel": "⏰ "}
        text = "\n".join(prefix[who] + line for who, line in self.lines[-3:])
        self.hud_canvas.itemconfigure(self.hud_items["log"], text=text)

    def _render_info(self) -> None:
        if self.hud is None or not hasattr(self, "hud_items"):
            return
        c, info = self.hud_canvas, self.info
        c.itemconfigure(self.hud_items["weather"], text=info.get("weather", ""))
        reminders = info.get("reminders") or ["Rien de prévu"]
        c.itemconfigure(self.hud_items["reminders"], text="\n\n".join(reminders[:5]))
        c.itemconfigure(self.hud_items["news"], text="\n\n".join(f"{i}. {t}" for i, t in
                                                                 enumerate(info.get("news", [])[:5], 1)))
        status = info.get("status") or {}
        parts = []
        if "cpu" in status:
            parts.append(f"CPU  {_bar(status['cpu'])} {status['cpu']:3d} %")
            parts.append(f"RAM  {_bar(status['ram'])} {status['ram']:3d} %")
        if "battery" in status:
            plug = " ⚡" if status.get("plugged") else ""
            parts.append(f"BAT  {_bar(status['battery'])} {status['battery']:3d} %{plug}")
        c.itemconfigure(self.hud_items["status"], text="\n".join(parts))

    def _tick(self) -> None:
        state = "stage" if self.stage_mode and self.state == "idle" else self.state
        for reactor in (getattr(self, "widget_reactor", None), getattr(self, "hud_reactor", None)):
            if reactor is not None:
                reactor.state = state
                reactor.step()
        if self.hud is not None and hasattr(self, "hud_items"):
            now = datetime.now()
            c = self.hud_canvas
            c.itemconfigure(self.hud_items["clock"], text=now.strftime("%H:%M"))
            c.itemconfigure(self.hud_items["date"],
                            text=f"{WEEKDAYS[now.weekday()]} {now.day} {MONTHS[now.month - 1]} {now.year}")
            labels = {"idle": "EN ATTENTE — dites « Viky »", "listening": "À L'ÉCOUTE…",
                      "thinking": "RÉFLEXION…", "speaking": "", "stage": "MODE SPECTACLE"}
            c.itemconfigure(self.hud_items["state"], text=labels.get(state, ""),
                            fill=STATE_COLORS.get(state, CYAN))
        self.loop.root.after(33, self._tick)

    # ------------------------------------------------------------ actions

    def _on_enter(self, event) -> None:
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if text:
            threading.Thread(target=self.submit, args=(text,), daemon=True).start()

    def _quit(self) -> None:
        if self.on_quit:
            self.on_quit()

    def _refresh_data(self) -> None:
        """Rafraîchit météo, actualités, rappels et état du PC en arrière-plan."""
        last_slow = 0.0
        while True:
            try:
                slow = time.monotonic() - last_slow > 1800  # météo et titres : toutes les 30 min
                info = self.data(slow)
                if slow:
                    last_slow = time.monotonic()
                self.info.update({k: v for k, v in info.items() if v is not None})
                self.loop.call(self._render_info)
            except Exception as error:
                print(f"[Viky] Données du HUD indisponibles : {error}")
            time.sleep(5)


def _bar(percent: int, width: int = 12) -> str:
    filled = round(percent / 100 * width)
    return "█" * filled + "░" * (width - filled)
