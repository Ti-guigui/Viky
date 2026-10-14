"""Actions concrètes sur l'ordinateur.

Windows est la plateforme principale ; Linux et macOS ont des équivalents
de base qui seront améliorés plus tard.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from .text import normalize

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
_PLATFORM = 0 if WINDOWS else 2 if MAC else 1

# nom prononcé -> (commande Windows, commande Linux, application macOS)
APPS: dict[str, tuple[str | None, str | None, str | None]] = {}


def _add_app(names: list[str], win: str | None, linux: str | None, mac: str | None) -> None:
    for name in names:
        APPS[name] = (win, linux, mac)


_add_app(["bloc notes", "notepad"], "notepad", "gedit", "TextEdit")
_add_app(["calculatrice", "calculette", "calculator"], "calc", "gnome-calculator", "Calculator")
_add_app(["paint"], "mspaint", None, None)
_add_app(["explorateur", "explorateur de fichiers", "explorateur windows", "file explorer", "files"],
         "explorer", "nautilus", "Finder")
_add_app(["chrome", "google chrome"], "chrome", "google-chrome", "Google Chrome")
_add_app(["edge", "microsoft edge"], "msedge", "microsoft-edge", "Microsoft Edge")
_add_app(["firefox"], "firefox", "firefox", "Firefox")
_add_app(["vs code", "vscode", "visual studio code", "code"], "code", "code", "Visual Studio Code")
_add_app(["word"], "winword", "libreoffice --writer", "Microsoft Word")
_add_app(["excel"], "excel", "libreoffice --calc", "Microsoft Excel")
_add_app(["powerpoint"], "powerpnt", "libreoffice --impress", "Microsoft PowerPoint")
_add_app(["terminal", "invite de commande", "invite de commandes", "command prompt"],
         "cmd", "x-terminal-emulator", "Terminal")
_add_app(["parametres", "reglages", "settings"], "ms-settings:", "gnome-control-center", "System Settings")
_add_app(["gestionnaire des taches", "task manager"], "taskmgr", "gnome-system-monitor", "Activity Monitor")

# Nom du processus Windows à fermer pour chaque commande connue.
_WIN_PROCESSES = {
    "notepad": "notepad.exe", "calc": "CalculatorApp.exe", "mspaint": "mspaint.exe",
    "chrome": "chrome.exe", "msedge": "msedge.exe", "firefox": "firefox.exe", "code": "Code.exe",
    "winword": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpnt": "POWERPNT.EXE",
    "taskmgr": "Taskmgr.exe", "cmd": "cmd.exe",
}
# Fermer ces processus casserait Windows : on refuse.
_PROTECTED = {"explorer", "explorer.exe", "ms-settings:"}

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "wikipedia": "https://fr.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.fr",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "claude": "https://claude.ai",
    "meteo": "https://www.google.com/search?q=m%C3%A9t%C3%A9o",
    "weather": "https://www.google.com/search?q=weather",
}

# nom prononcé -> dossier dans le répertoire de l'utilisateur
FOLDERS = {
    "documents": "Documents",
    "telechargements": "Downloads", "downloads": "Downloads",
    "bureau": "Desktop", "desktop": "Desktop",
    "images": "Pictures", "photos": "Pictures", "pictures": "Pictures",
    "musique": "Music", "music": "Music",
    "videos": "Movies" if MAC else "Videos",
}

CAMERA = {"camera", "webcam", "appareil photo"}

_DETERMINERS = re.compile(
    r"^(le site( web| internet)?|le logiciel|l application|l appli|le programme|le dossier|"
    r"the website|the app|the folder|mes|mon|ma|les|le|la|l|un|une|the|my)\s+"
)
_TRAILING = re.compile(r"\s+(sur internet|dans le navigateur|in the browser|please)$")


def clean_target(target: str) -> str:
    target = normalize(target)
    previous = None
    while previous != target:
        previous = target
        target = _DETERMINERS.sub("", target)
        target = _TRAILING.sub("", target)
    return target


def resolve_target(target: str, apps: dict[str, str] | None = None,
                   sites: dict[str, str] | None = None) -> tuple[str, str]:
    """Devine ce que l'utilisateur veut ouvrir.

    Renvoie (genre, valeur) où genre vaut « camera », « folder », « site » ou « app ».
    """
    name = clean_target(target)
    apps, sites = apps or {}, sites or {}

    # Les noms choisis par l'utilisateur peuvent commencer par « mon », « le »…
    for key in (normalize(target), name):
        if key in apps:
            return "app", apps[key]
        if key in sites:
            return "site", sites[key]
    if name in CAMERA:
        return "camera", name
    if name in FOLDERS:
        return "folder", str(user_dir(FOLDERS[name]))
    if name in SITES:
        return "site", SITES[name]
    domain = re.sub(r" ?point ", ".", name).replace(" ", "")
    if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
        return "site", f"https://{domain}"
    if name in APPS and APPS[name][_PLATFORM]:
        return "app", APPS[name][_PLATFORM]
    return "app", name


def user_dir(name: str) -> Path:
    """Trouve un dossier personnel, y compris s'il est synchronisé par OneDrive."""
    home = Path.home()
    for candidate in (home / name, home / "OneDrive" / name):
        if candidate.exists():
            return candidate
    return home / name


def _viky_dir(base: str) -> Path:
    folder = user_dir(base) / "Viky"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------- ouverture

def open_target(target: str, apps: dict[str, str] | None = None,
                sites: dict[str, str] | None = None) -> bool:
    kind, value = resolve_target(target, apps, sites)
    if kind == "site":
        return webbrowser.open(value)
    if kind == "folder":
        Path(value).mkdir(parents=True, exist_ok=True)
        return _open_path(value)
    if kind == "camera":
        return open_camera()
    return launch_app(value)


def _open_path(path: str) -> bool:
    if WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if MAC else "xdg-open", path])
    return True


def open_camera() -> bool:
    if WINDOWS:
        os.startfile("microsoft.windows.camera:")  # type: ignore[attr-defined]
        return True
    if MAC:
        return subprocess.call(["open", "-a", "Photo Booth"]) == 0
    return launch_app("cheese")


def launch_app(command: str) -> bool:
    if WINDOWS:
        return _launch_windows(command)
    if MAC:
        return subprocess.call(["open", "-a", command]) == 0
    parts = command.split()
    if shutil.which(parts[0]):
        subprocess.Popen(parts, start_new_session=True)
        return True
    return False


def _launch_windows(command: str) -> bool:
    if command.endswith(":") or command.startswith(("http://", "https://", "shell:")):
        os.startfile(command)  # type: ignore[attr-defined]
        return True
    path = Path(os.path.expandvars(command))
    if path.is_absolute() and path.exists():
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    exe = shutil.which(command) or _windows_app_path(command)
    if exe:
        subprocess.Popen(["cmd", "/c", "start", "", exe], creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    shortcut = _find_start_menu_shortcut(command)
    if shortcut:
        os.startfile(str(shortcut))  # type: ignore[attr-defined]
        return True
    return False


def _windows_app_path(name: str) -> str | None:
    """Cherche le programme dans la base de registre (« App Paths »), comme le menu Exécuter."""
    import winreg

    key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}.exe"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key_path) as key:
                return winreg.QueryValue(key, None)
        except OSError:
            continue
    return None


def _start_menu_shortcuts() -> dict[str, Path]:
    folders = [
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        user_dir("Desktop"),
    ]
    shortcuts: dict[str, Path] = {}
    for folder in folders:
        if folder.exists():
            for link in folder.rglob("*.lnk"):
                shortcuts.setdefault(normalize(link.stem), link)
    return shortcuts


def _find_start_menu_shortcut(name: str) -> Path | None:
    """Trouve un raccourci du menu Démarrer dont le nom ressemble à `name`."""
    return find_shortcut(name, _start_menu_shortcuts())


def find_shortcut(name: str, shortcuts: dict[str, Path]) -> Path | None:
    if name in shortcuts:
        return shortcuts[name]
    starting = [key for key in shortcuts if key.startswith(name + " ")]
    if starting:
        return shortcuts[min(starting, key=len)]
    close = difflib.get_close_matches(name, list(shortcuts), n=1, cutoff=0.75)
    return shortcuts[close[0]] if close else None


# ---------------------------------------------------------------- fermeture

def close_app(target: str, apps: dict[str, str] | None = None) -> bool:
    kind, command = resolve_target(target, apps)
    if kind != "app" or command in _PROTECTED:
        return False
    if WINDOWS:
        exe = Path(command).name if command.lower().endswith(".exe") else command
        process = _WIN_PROCESSES.get(exe, exe.replace(" ", "") + ("" if exe.endswith(".exe") else ".exe"))
        if process.lower() in _PROTECTED:
            return False
        return subprocess.call(["taskkill", "/IM", process], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW) == 0
    if MAC:
        return subprocess.call(["osascript", "-e", f'quit app "{command}"']) == 0
    return subprocess.call(["pkill", "-f", command.split()[0]]) == 0


# ---------------------------------------------------------------- internet

def web_search(query: str) -> bool:
    return webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")


def youtube_search(query: str) -> bool:
    return webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")


# ---------------------------------------------------------------- système

_VK_VOLUME = {"mute": 0xAD, "down": 0xAE, "up": 0xAF}


def volume(direction: str) -> bool:
    """Monte (« up »), baisse (« down ») ou coupe/rétablit (« mute ») le son."""
    if WINDOWS:
        import ctypes

        presses = 1 if direction == "mute" else 5  # chaque appui = 2 %
        for _ in range(presses):
            ctypes.windll.user32.keybd_event(_VK_VOLUME[direction], 0, 0, 0)
            ctypes.windll.user32.keybd_event(_VK_VOLUME[direction], 0, 2, 0)
        return True
    if MAC:
        script = {
            "up": "set volume output volume ((output volume of (get volume settings)) + 10)",
            "down": "set volume output volume ((output volume of (get volume settings)) - 10)",
            "mute": "set volume output muted (not (output muted of (get volume settings)))",
        }[direction]
        return subprocess.call(["osascript", "-e", script]) == 0
    arg = {"up": ["set-sink-volume", "@DEFAULT_SINK@", "+10%"],
           "down": ["set-sink-volume", "@DEFAULT_SINK@", "-10%"],
           "mute": ["set-sink-mute", "@DEFAULT_SINK@", "toggle"]}[direction]
    return shutil.which("pactl") is not None and subprocess.call(["pactl", *arg]) == 0


def lock_screen() -> bool:
    if WINDOWS:
        import ctypes

        return bool(ctypes.windll.user32.LockWorkStation())
    if MAC:
        return subprocess.call(["pmset", "displaysleepnow"]) == 0
    return subprocess.call(["loginctl", "lock-session"]) == 0


def screenshot() -> Path | None:
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    path = _viky_dir("Pictures") / f"capture_{_stamp()}.png"
    ImageGrab.grab().save(path)
    return path


def take_photo() -> Path | None:
    try:
        import cv2
    except ImportError:
        return None
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW) if WINDOWS else cv2.VideoCapture(0)
    try:
        if not camera.isOpened():
            return None
        frame = None
        for _ in range(15):  # laisse la caméra régler son exposition
            ok, frame = camera.read()
        if frame is None:
            return None
        path = _viky_dir("Pictures") / f"photo_{_stamp()}.jpg"
        cv2.imwrite(str(path), frame)
        return path
    finally:
        camera.release()


def add_note(text: str) -> Path:
    path = _viky_dir("Documents") / "notes.txt"
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%d/%m/%Y %H:%M}] {text}\n")
    return path
