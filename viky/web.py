"""Petits outils réseau communs (sans dépendance externe)."""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Viky/0.2"


def get(url: str, timeout: float = 8.0, attempts: int = 3) -> bytes:
    """Télécharge une page ; réessaie si le service est momentanément indisponible."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(1 + attempt)
    raise AssertionError("inaccessible")


def get_json(url: str, timeout: float = 8.0):
    return json.loads(get(url, timeout))


def html_to_text(page: str) -> str:
    """Extrait le texte lisible d'une page web (titres et paragraphes)."""
    page = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>", " ", page)
    blocks = re.findall(r"(?is)<(?:p|h1|h2|h3|li)[^>]*>(.*?)</(?:p|h1|h2|h3|li)>", page)
    text = "\n".join(strip_tags(b) for b in blocks)
    return re.sub(r"\n{2,}", "\n", text).strip()


def strip_tags(fragment: str) -> str:
    text = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
