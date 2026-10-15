"""Contrôle du PC : état de la machine, luminosité, musique, fenêtres, alimentation."""

from __future__ import annotations

import re
import subprocess
import sys

WINDOWS = sys.platform == "win32"

# Touches virtuelles Windows
_VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2,
       "win": 0x5B, "d": 0x44, "alt": 0x12, "tab": 0x09, "f4": 0x73, "up": 0x26, "down": 0x28}


class NotSupported(Exception):
    pass


def beep() -> None:
    """Petit signal sonore pour les rappels et minuteurs."""
    if WINDOWS:
        import winsound

        for _ in range(3):
            winsound.Beep(880, 180)


def _press(*keys: str) -> None:
    if not WINDOWS:
        raise NotSupported
    import ctypes

    user32 = ctypes.windll.user32
    for key in keys:
        user32.keybd_event(_VK[key], 0, 0, 0)
    for key in reversed(keys):
        user32.keybd_event(_VK[key], 0, 2, 0)


def _run(*command: str) -> str:
    flags = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
    return subprocess.run(command, capture_output=True, text=True, errors="ignore",
                          creationflags=flags, timeout=15).stdout


# ---------------------------------------------------------------- état

def status() -> dict:
    """Batterie, processeur et mémoire."""
    import psutil

    info = {"cpu": round(psutil.cpu_percent(interval=0.5)),
            "ram": round(psutil.virtual_memory().percent)}
    battery = psutil.sensors_battery()
    if battery is not None:
        info["battery"] = round(battery.percent)
        info["plugged"] = bool(battery.power_plugged)
    return info


def wifi_name() -> str | None:
    """Nom du réseau Wi-Fi connecté (Windows)."""
    if not WINDOWS:
        raise NotSupported
    match = re.search(r"^\s*SSID\s*:\s*(.+)$", _run("netsh", "wlan", "show", "interfaces"), re.M)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------- écran

def brightness(change: int | None = None, level: int | None = None) -> int:
    """Change la luminosité (en relatif ou à un niveau donné) et renvoie le nouveau niveau."""
    import screen_brightness_control as sbc

    current = sbc.get_brightness(display=0)[0]
    target = level if level is not None else current + (change or 0)
    target = max(0, min(100, target))
    sbc.set_brightness(target, display=0)
    return target


# ---------------------------------------------------------------- musique et fenêtres

def media(action: str) -> None:
    """play_pause, next, previous, stop : fonctionne avec Spotify, YouTube, le lecteur Windows…"""
    _press(action)


def show_desktop() -> None:
    _press("win", "d")


def switch_window() -> None:
    _press("alt", "tab")


def maximize_window() -> None:
    _press("win", "up")


def minimize_window() -> None:
    _press("win", "down")


# ---------------------------------------------------------------- alimentation

def power(action: str) -> None:
    """shutdown, restart, sleep ou cancel (annule un arrêt programmé)."""
    if not WINDOWS:
        raise NotSupported
    if action == "shutdown":
        _run("shutdown", "/s", "/t", "15")
    elif action == "restart":
        _run("shutdown", "/r", "/t", "15")
    elif action == "cancel":
        _run("shutdown", "/a")
    elif action == "sleep":
        _run("rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0")
