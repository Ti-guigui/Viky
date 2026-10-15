"""E-mails Gmail et iCloud : lire les nouveaux messages, en écouter un, en envoyer (avec pièce jointe).

Connexion par IMAP (lecture) et SMTP (envoi) avec un « mot de passe d'application »
créé dans votre compte Google ou Apple. Le mot de passe est rangé dans le
Gestionnaire d'identification de Windows, jamais dans un fichier.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import mimetypes
import re
import smtplib
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, parseaddr, parsedate_to_datetime
from pathlib import Path

from .web import html_to_text

PROVIDERS = {
    "gmail": {"imap": "imap.gmail.com", "smtp": "smtp.gmail.com", "port": 587},
    "icloud": {"imap": "imap.mail.me.com", "smtp": "smtp.mail.me.com", "port": 587},
}


@dataclass
class Account:
    provider: str  # « gmail » ou « icloud »
    address: str
    password: str = field(repr=False, default="")

    @property
    def label(self) -> str:
        return "Gmail" if self.provider == "gmail" else "iCloud"


@dataclass
class Mail:
    account: Account
    uid: str
    sender: str  # nom affiché, ou adresse
    address: str
    subject: str
    date: object = None


def decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _imap(account: Account) -> imaplib.IMAP4_SSL:
    connection = imaplib.IMAP4_SSL(PROVIDERS[account.provider]["imap"])
    connection.login(account.address, account.password)
    connection.select("INBOX", readonly=True)  # lecture seule : les messages ne passent pas en « lu »
    return connection


def parse_headers(raw: bytes) -> tuple[str, str, str, object]:
    message = email.message_from_bytes(raw)
    name, address = parseaddr(decode(message.get("From")))
    try:
        date = parsedate_to_datetime(message.get("Date"))
    except (TypeError, ValueError):
        date = None
    return name or address, address, decode(message.get("Subject")) or "(sans objet)", date


def unread(account: Account, limit: int = 5) -> tuple[int, list[Mail]]:
    """Nombre de messages non lus, et les plus récents."""
    connection = _imap(account)
    try:
        _, data = connection.uid("search", None, "UNSEEN")
        uids = data[0].split()
        mails = []
        for uid in reversed(uids[-limit:]):
            _, parts = connection.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), b"")
            sender, address, subject, date = parse_headers(raw)
            mails.append(Mail(account, uid.decode(), sender, address, subject, date))
        return len(uids), mails
    finally:
        connection.logout()


def message_text(raw: bytes, max_chars: int = 4000) -> str:
    """Texte lisible d'un message (partie texte, ou HTML converti)."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        content = html_to_text(content)
    content = re.sub(r"(?m)^>.*$", "", content)  # retire les anciens messages cités
    return re.sub(r"\n{3,}", "\n\n", content).strip()[:max_chars]


def body(mail: Mail) -> str:
    connection = _imap(mail.account)
    try:
        _, parts = connection.uid("fetch", mail.uid, "(BODY.PEEK[])")
        raw = next((p[1] for p in parts if isinstance(p, tuple)), b"")
        return message_text(raw)
    finally:
        connection.logout()


def build_message(account: Account, to: str, subject: str, text: str, sender_name: str = "",
                  attachments: list[Path] | None = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((sender_name, account.address)) if sender_name else account.address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    for path in attachments or []:
        kind, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (kind or "application/octet-stream").split("/", 1)
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return message


def send(account: Account, message: EmailMessage) -> None:
    settings = PROVIDERS[account.provider]
    with smtplib.SMTP(settings["smtp"], settings["port"], timeout=30) as server:
        server.starttls()
        server.login(account.address, account.password)
        server.send_message(message)


def spoken_address(text: str) -> str | None:
    """« paul point martin arobase gmail point com » -> « paul.martin@gmail.com »."""
    text = text.lower().strip()
    text = re.sub(r"\s*(arobase|at)\s*", "@", text)
    text = re.sub(r"\s*(point|dot)\s*", ".", text)
    text = re.sub(r"\s*(tiret|dash)\s*", "-", text)
    text = text.replace(" ", "")
    return text if re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", text) else None
