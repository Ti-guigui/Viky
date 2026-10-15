import types
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import pytest

from viky import mail
from viky.accounts import _update_config
from viky.agenda import Event, day_range, events_from_ics
from viky.assistant import Assistant
from viky.config import Config
from viky.memory import Memory
from viky.reminders import Reminders


def raw_message(sender, subject, text=None, html=None):
    message = EmailMessage()
    message["From"] = sender
    message["Subject"] = subject
    message["Date"] = "Thu, 15 Oct 2026 09:30:00 +0200"
    if text:
        message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html") if text else message.set_content(html, subtype="html")
    return message.as_bytes()


class FakeIMAP:
    """Imite imaplib.IMAP4_SSL avec trois messages, dont deux non lus."""

    messages = {
        b"1": raw_message("Lu <lu@x.fr>", "Déjà lu", "x"),
        b"2": raw_message("=?utf-8?q?Am=C3=A9lie_Martin?= <amelie@x.fr>", "=?utf-8?q?R=C3=A9p=C3=A9tition?=",
                          "Bonjour,\n\nOn se voit à 18h ?\n\n> ancien message cité"),
        b"3": raw_message("paul@x.fr", "Facture", html="<html><body><p>Votre <b>facture</b> est prête.</p></body></html>"),
    }
    logged = []

    def __init__(self, host):
        self.host = host

    def login(self, user, password):
        FakeIMAP.logged.append((self.host, user, password))

    def select(self, box, readonly=False):
        assert readonly  # Viky ne doit jamais marquer les messages comme lus

    def uid(self, command, *args):
        if command == "search":
            return "OK", [b"2 3"]
        uid, what = args
        uid = uid if isinstance(uid, bytes) else uid.encode()
        raw = self.messages[uid]
        if "HEADER" in what:
            raw = raw.split(b"\n\n")[0] + b"\n\n"
        return "OK", [(b"header", raw), b")"]

    def logout(self):
        pass


@pytest.fixture
def account(monkeypatch):
    monkeypatch.setattr(mail.imaplib, "IMAP4_SSL", FakeIMAP)
    return mail.Account("gmail", "moi@gmail.com", "motdepasse")


def test_unread_and_body(account):
    count, mails = mail.unread(account)
    assert count == 2
    assert [(m.sender, m.subject) for m in mails] == [("paul@x.fr", "Facture"), ("Amélie Martin", "Répétition")]
    assert FakeIMAP.logged[-1] == ("imap.gmail.com", "moi@gmail.com", "motdepasse")
    assert mail.body(mails[1]) == "Bonjour,\n\nOn se voit à 18h ?"
    assert mail.body(mails[0]) == "Votre facture est prête."


def test_build_message_with_attachment(tmp_path):
    pdf = tmp_path / "contrat.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    account = mail.Account("icloud", "moi@icloud.com")
    message = mail.build_message(account, "paul@x.fr", "Contrat", "Voici le contrat.", "Guillaume", [pdf])
    assert message["From"] == "Guillaume <moi@icloud.com>"
    attachments = list(message.iter_attachments())
    assert attachments[0].get_filename() == "contrat.pdf"
    assert attachments[0].get_content_type() == "application/pdf"


@pytest.mark.parametrize("text, address", [
    ("paul point martin arobase gmail point com", "paul.martin@gmail.com"),
    ("jean tiret luc arobase icloud point com", "jean-luc@icloud.com"),
    ("paul", None),
])
def test_spoken_address(text, address):
    assert mail.spoken_address(text) == address


ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1
DTSTART;TZID=Europe/Paris:20261015T090000
DTEND;TZID=Europe/Paris:20261015T100000
SUMMARY:Dentiste
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20261016
DTEND;VALUE=DATE:20261017
SUMMARY:Anniversaire de Marie
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;TZID=Europe/Paris:20261005T190000
DTEND;TZID=Europe/Paris:20261005T210000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Club de magie
END:VEVENT
END:VCALENDAR
"""


def test_events_from_ics():
    events = events_from_ics(ICS, datetime(2026, 10, 15), datetime(2026, 10, 22), "Google")
    titles = [(e.title, e.all_day) for e in sorted(events, key=lambda e: e.start)]
    assert titles == [("Dentiste", False), ("Anniversaire de Marie", True), ("Club de magie", False)]
    club = next(e for e in events if e.title == "Club de magie")
    assert club.start.weekday() == 0 and club.start.day == 19  # répétition du lundi suivant


@pytest.mark.parametrize("text, days, label", [
    ("qu est ce que j ai demain", (16, 17), "demain"),
    ("mon agenda", (15, 16), "aujourd'hui"),
    ("qu est ce que j ai lundi", (19, 20), "lundi"),
    ("qu est ce que j ai ce week end", (17, 19), "ce week-end"),
])
def test_day_range(text, days, label):
    now = datetime(2026, 10, 15, 8, 0)  # un jeudi
    start, end, name = day_range(text, now)
    assert (start.day if name != "aujourd'hui" else 15, end.day, name) == (*days, label)


def test_update_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[comptes]\n# gmail = "vous@gmail.com"\nenvoi = "gmail"\n', encoding="utf-8")
    _update_config(path, {"gmail": "moi@gmail.com", "icloud": "moi@icloud.com"})
    text = path.read_text(encoding="utf-8")
    assert 'gmail = "moi@gmail.com"' in text and 'icloud = "moi@icloud.com"' in text
    assert "# gmail" not in text


# ------------------------------------------------------------ Viky

class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


class FakeAgenda:
    configured = True
    can_add = True

    def __init__(self):
        self.added = []

    def events(self, start, end):
        return [Event("Dentiste", start.replace(hour=9, minute=0), start.replace(hour=10)),
                Event("Répétition", start.replace(hour=18, minute=30), start.replace(hour=20))]

    def add(self, title, start, duration=timedelta(hours=1)):
        self.added.append((title, start))
        return "Domicile"


@pytest.fixture
def viky(tmp_path, monkeypatch):
    sent = []
    account = mail.Account("gmail", "moi@gmail.com", "x")
    mailer = types.SimpleNamespace(
        unread=lambda acc, limit=5: (1, [mail.Mail(acc, "7", "Amélie", "a@x.fr", "Répétition",
                                                    datetime(2026, 10, 15))]),
        body=lambda m: "On se voit à 18h ?",
        build_message=mail.build_message, spoken_address=mail.spoken_address,
        send=lambda acc, message: sent.append(message))
    config = Config()
    config.contacts = {"paul": "paul@x.fr"}
    monkeypatch.setattr(Config, "mail_accounts", lambda self: [account])
    speaker = FakeSpeaker()
    contract = tmp_path / "Contrat Paul.pdf"
    contract.write_bytes(b"%PDF-1.4")
    files = types.SimpleNamespace(find=lambda s: contract if "contrat" in s else None)
    brain = types.SimpleNamespace(available=False, use_claude=False, history=[], persona=None, context=None)
    assistant = Assistant(config, speaker, types.SimpleNamespace(), types.SimpleNamespace(NotAvailable=RuntimeError),
                          files=files, brain=brain, stage=types.SimpleNamespace(),
                          memory=Memory(tmp_path / "m.json"), reminders=Reminders(tmp_path / "r.json"),
                          agenda=FakeAgenda(), mailer=mailer)
    return assistant, speaker, sent


def say(assistant, text, wake=False):
    assistant.on_utterance({"fr": text}, require_wake=wake)


def test_mail_check_and_read(viky):
    assistant, speaker, _ = viky
    say(assistant, "est-ce que j'ai des nouveaux mails ?")
    assert speaker.said[:2] == ["Vous avez 1 e-mail(s) non lu(s).", "1. De Amélie : Répétition."]
    say(assistant, "lis le mail numéro un")
    assert speaker.said[-2:] == ["E-mail de Amélie, objet : Répétition.", "On se voit à 18h ?"]


def test_mail_dictation_and_confirmation(viky):
    assistant, speaker, sent = viky
    say(assistant, "Viky, envoie un mail à Paul", wake=True)
    assert speaker.said[-1] == "Que voulez-vous écrire à Paul ?"
    say(assistant, "je serai en retard de dix minutes", wake=True)  # réponse, sans redire « Viky »
    assert speaker.said[-1].startswith("J'envoie à Paul, depuis Gmail : « Je serai en retard de dix minutes »")
    assert sent == []
    say(assistant, "confirme", wake=True)
    assert speaker.said[-1] == "C'est envoyé à Paul."
    assert sent[0]["To"] == "paul@x.fr" and "Je serai en retard" in sent[0].get_content()


def test_mail_cancel(viky):
    assistant, speaker, sent = viky
    say(assistant, "envoie un mail à Paul pour lui dire que le spectacle est annulé")
    say(assistant, "annule")
    assert sent == [] and speaker.said[-1] == "D'accord, j'annule."


def test_mail_with_file(viky):
    assistant, speaker, sent = viky
    say(assistant, "envoie le pdf contrat à paul")
    assert "Contrat Paul.pdf" in speaker.said[-1]
    say(assistant, "confirme")
    assert sent[0]["Subject"] == "Contrat Paul"


def test_unknown_contact(viky):
    assistant, speaker, _ = viky
    say(assistant, "envoie un mail à Bernard")
    assert speaker.said[-1].startswith("Je ne connais pas l'adresse de bernard")


def test_agenda(viky):
    assistant, speaker, _ = viky
    say(assistant, "qu'est-ce que j'ai demain ?")
    assert speaker.said == ["Demain, vous avez 2 rendez-vous.", "à 9 h : Dentiste", "à 18 h 30 : Répétition"]
    say(assistant, "ajoute un rendez-vous chez le dentiste demain à 9h")
    title, start = assistant.agenda.added[0]
    assert title == "Chez le dentiste" and (start.hour, start.minute) == (9, 0)
    assert speaker.said[-1].startswith("C'est ajouté à votre calendrier Domicile : Chez le dentiste, demain à 9 h")
