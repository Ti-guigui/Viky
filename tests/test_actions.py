from pathlib import Path

from viky import actions
from viky.actions import clean_target, find_shortcut, resolve_target


def test_clean_target():
    assert clean_target("le bloc notes") == "bloc notes"
    assert clean_target("l'application Spotify") == "spotify"
    assert clean_target("mes téléchargements") == "telechargements"


def test_known_site():
    assert resolve_target("YouTube") == ("site", "https://www.youtube.com")


def test_spoken_domain():
    assert resolve_target("le site wikipedia point org") == ("site", "https://wikipedia.org")
    assert resolve_target("lemonde.fr") == ("site", "https://lemonde.fr")


def test_folder():
    kind, path = resolve_target("mes téléchargements")
    assert kind == "folder" and Path(path).name == "Downloads"


def test_camera():
    assert resolve_target("la caméra")[0] == "camera"


def test_builtin_app(monkeypatch):
    monkeypatch.setattr(actions, "_PLATFORM", 0)
    assert resolve_target("le bloc-notes") == ("app", "notepad")
    assert resolve_target("Visual Studio Code") == ("app", "code")


def test_user_config_wins():
    apps = {"mon jeu": r"C:\Jeux\jeu.exe"}
    assert resolve_target("mon jeu", apps) == ("app", r"C:\Jeux\jeu.exe")


def test_unknown_app_kept_as_is():
    assert resolve_target("Spotify") == ("app", "spotify")


def test_find_shortcut():
    shortcuts = {"spotify": Path("a"), "discord": Path("b"), "microsoft teams classic": Path("c"),
                 "microsoft teams": Path("d")}
    assert find_shortcut("spotify", shortcuts) == Path("a")
    assert find_shortcut("discorde", shortcuts) == Path("b")
    assert find_shortcut("microsoft", shortcuts) == Path("d")
    assert find_shortcut("photoshop", shortcuts) is None
