"""Projecteur (2e écran) et pilotage de PowerPoint / Excel sous Windows.

Le projecteur branché en HDMI est vu par Windows comme un deuxième écran.
Viky y déplace les fenêtres, lance les diaporamas dessus et pilote Office
par COM (pywin32). Hors Windows, ces fonctions renvoient False.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

WINDOWS = sys.platform == "win32"

# Touches virtuelles Windows
VK = {"right": 0x27, "left": 0x25, "pagedown": 0x22, "pageup": 0x21, "f11": 0x7A,
      "f5": 0x74, "escape": 0x1B, "alt": 0x12, "f4": 0x73, "b": 0x42, "w": 0x57}


class NotAvailable(Exception):
    """La fonction demandée n'existe pas sur ce système ou ce logiciel n'est pas ouvert."""


# ---------------------------------------------------------------- écrans

def monitors() -> list[dict]:
    """Liste les écrans : [{"rect": (gauche, haut, droite, bas), "primary": bool, "device": nom}]."""
    if not WINDOWS:
        return []
    import ctypes
    from ctypes import wintypes

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    found: list[dict] = []
    user32 = ctypes.windll.user32

    def callback(hmonitor, hdc, rect, data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            found.append({"rect": (r.left, r.top, r.right, r.bottom),
                          "primary": bool(info.dwFlags & 1), "device": info.szDevice})
        return True

    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors(None, None, proc(callback), 0)
    found.sort(key=lambda m: not m["primary"])
    return found


def projector() -> dict | None:
    """Le projecteur = le premier écran qui n'est pas l'écran principal."""
    screens = monitors()
    return screens[1] if len(screens) > 1 else None


def set_display_mode(mode: str) -> bool:
    """mode : « clone » (dupliquer), « extend » (étendre), « external », « internal »."""
    if not WINDOWS:
        return False
    subprocess.Popen(["DisplaySwitch.exe", f"/{mode}"])
    return True


# ---------------------------------------------------------------- fenêtres

def foreground() -> int:
    if not WINDOWS:
        return 0
    import ctypes

    return ctypes.windll.user32.GetForegroundWindow()


def move_to_projector(hwnd: int) -> bool:
    screen = projector()
    if not screen or not hwnd:
        return False
    import ctypes

    user32 = ctypes.windll.user32
    left, top, right, bottom = screen["rect"]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.MoveWindow(hwnd, left + 50, top + 50, (right - left) - 100, (bottom - top) - 100, True)
    user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
    return True


def wait_new_window(previous: int, timeout: float = 15.0) -> int:
    """Attend qu'une nouvelle fenêtre passe au premier plan (le fichier vient de s'ouvrir)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        hwnd = foreground()
        if hwnd and hwnd != previous:
            time.sleep(0.8)  # laisse l'application finir de s'afficher
            return foreground()
        time.sleep(0.2)
    return foreground()  # le fichier s'est peut-être ouvert dans une fenêtre déjà active


def press(*keys: str) -> None:
    """Appuie sur une combinaison de touches dans la fenêtre au premier plan."""
    if not WINDOWS:
        raise NotAvailable
    import ctypes

    user32 = ctypes.windll.user32
    for key in keys:
        user32.keybd_event(VK[key], 0, 0, 0)
    for key in reversed(keys):
        user32.keybd_event(VK[key], 0, 2, 0)


def open_file(path: Path, on_projector: bool) -> bool:
    """Ouvre un fichier avec son logiciel habituel, éventuellement sur le projecteur."""
    if not WINDOWS:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        return True
    if on_projector and path.suffix.lower() in (".pptx", ".ppt", ".ppsx", ".pps", ".pptm"):
        return start_slideshow(path)
    previous = foreground()
    os.startfile(str(path))  # type: ignore[attr-defined]
    if on_projector:
        hwnd = wait_new_window(previous)
        return move_to_projector(hwnd)
    return True


def project_current_window() -> bool:
    return move_to_projector(foreground())


# ---------------------------------------------------------------- Office (COM)

def _com(app_name: str, create: bool = False):
    if not WINDOWS:
        raise NotAvailable
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        return win32com.client.GetActiveObject(app_name)
    except Exception:
        if not create:
            raise NotAvailable
        app = win32com.client.Dispatch(app_name)
        app.Visible = True
        return app


def _set_slideshow_monitor(device: str) -> None:
    """Indique à PowerPoint sur quel écran projeter le diaporama."""
    import winreg

    for version in ("16.0", "15.0"):
        key_path = rf"Software\Microsoft\Office\{version}\PowerPoint\Options"
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisplayMonitor", 0, winreg.REG_SZ, device)
        except OSError:
            continue


def start_slideshow(path: Path | None = None, presenter_view: bool = False) -> bool:
    screen = projector()
    if screen:
        _set_slideshow_monitor(screen["device"])
    app = _com("PowerPoint.Application", create=True)
    if path is not None:
        presentation = app.Presentations.Open(str(path), False, False, True)
    elif app.Presentations.Count:
        presentation = app.ActivePresentation
    else:
        raise NotAvailable
    settings = presentation.SlideShowSettings
    settings.ShowPresenterView = -1 if presenter_view and screen else 0
    settings.Run()
    return True


def _show_view():
    app = _com("PowerPoint.Application")
    if app.SlideShowWindows.Count == 0:
        raise NotAvailable
    return app.SlideShowWindows(1).View


def slideshow_running() -> bool:
    try:
        _show_view()
        return True
    except Exception:
        return False


def slide_next() -> None:
    _show_view().Next()


def slide_previous() -> None:
    _show_view().Previous()


def slide_goto(number: int) -> None:
    _show_view().GotoSlide(number)


def slideshow_black(black: bool) -> None:
    _show_view().State = 3 if black else 1  # ppSlideShowBlackScreen / ppSlideShowRunning


def slideshow_end() -> None:
    _show_view().Exit()


def set_slide_title(text: str) -> None:
    app = _com("PowerPoint.Application")
    try:
        slide = _show_view().Slide
    except NotAvailable:
        slide = app.ActiveWindow.View.Slide
    if not slide.Shapes.HasTitle:
        raise NotAvailable
    slide.Shapes.Title.TextFrame.TextRange.Text = text


def _excel():
    app = _com("Excel.Application")
    if app.Workbooks.Count == 0:
        raise NotAvailable
    return app


def excel_set(cell: str, value) -> None:
    _excel().ActiveSheet.Range(cell).Value = value


def excel_get(cell: str):
    return _excel().ActiveSheet.Range(cell).Value


def excel_sheet(step: int) -> str:
    app = _excel()
    sheets = app.ActiveWorkbook.Worksheets
    index = (app.ActiveSheet.Index - 1 + step) % sheets.Count + 1
    sheets(index).Activate()
    return app.ActiveSheet.Name


def save_active() -> None:
    """Enregistre le document Office ouvert (Excel, puis PowerPoint)."""
    for name in ("Excel.Application", "PowerPoint.Application"):
        try:
            app = _com(name)
        except Exception:
            continue
        if name.startswith("Excel") and app.Workbooks.Count:
            app.ActiveWorkbook.Save()
            return
        if name.startswith("PowerPoint") and app.Presentations.Count:
            app.ActivePresentation.Save()
            return
    raise NotAvailable
