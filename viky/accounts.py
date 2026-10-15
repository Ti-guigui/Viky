"""Comptes Gmail / iCloud et agendas : réglage guidé et mots de passe protégés.

Les mots de passe d'application et les adresses secrètes des agendas Google sont
rangés dans le Gestionnaire d'identification de Windows (bibliothèque keyring),
jamais dans config.toml.
"""

from __future__ import annotations

import getpass
from pathlib import Path

SERVICE = "Viky"


def secret(name: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICE, name)
    except Exception:
        return None


def store(name: str, value: str) -> None:
    import keyring

    keyring.set_password(SERVICE, name, value)


def setup(config_path: Path) -> None:
    """Assistant de configuration en mode texte (lancé par configurer_comptes.bat)."""
    from . import mail

    print("=== Configuration des comptes de Viky ===\n")
    print("Il faut des « mots de passe d'application » (pas votre mot de passe habituel) :")
    print("  - Gmail  : https://myaccount.google.com/apppasswords (validation en deux étapes requise)")
    print("  - iCloud : https://account.apple.com -> Connexion et sécurité -> Mots de passe pour les apps\n")
    lines: dict[str, str] = {}

    for provider in ("gmail", "icloud"):
        address = input(f"Adresse {provider.capitalize()} (Entrée pour passer) : ").strip()
        if not address:
            continue
        password = getpass.getpass("Mot de passe d'application (invisible à la saisie) : ").replace(" ", "")
        account = mail.Account(provider, address, password)
        try:
            mail.unread(account, limit=1)
            print(f"  Connexion {account.label} réussie.")
        except Exception as error:
            print(f"  Attention, la connexion a échoué ({error}). Vérifiez le mot de passe.")
        store(f"{provider}:{address}", password)
        lines[provider] = address

    print("\nGoogle Agenda : dans agenda.google.com -> Paramètres -> votre agenda ->")
    print("« Adresse secrète au format iCal ». Collez une ou plusieurs adresses (Entrée pour finir).")
    urls = []
    while True:
        url = input("Adresse iCal : ").strip()
        if not url:
            break
        urls.append(url)
    if urls:
        store("google_ical", "\n".join(urls))

    if lines:
        _update_config(config_path, lines)
    print("\nC'est terminé. Relancez Viky.")
    input("Appuyez sur Entrée pour fermer.")


def _update_config(config_path: Path, addresses: dict[str, str]) -> None:
    """Écrit les adresses (pas les mots de passe) dans la section [comptes] de config.toml."""
    import re

    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    for provider, address in addresses.items():
        line = f'{provider} = "{address}"'
        pattern = rf'(?m)^#?\s*{provider}\s*=.*$'
        if re.search(r"(?m)^\[comptes\]", text) and re.search(pattern, text.split("[comptes]", 1)[1]):
            head, tail = text.split("[comptes]", 1)
            text = head + "[comptes]" + re.sub(pattern, line, tail, count=1)
        elif "[comptes]" in text:
            text = text.replace("[comptes]", f"[comptes]\n{line}", 1)
        else:
            text += f"\n[comptes]\n{line}\n"
    config_path.write_text(text, encoding="utf-8")
