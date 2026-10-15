"""Grands titres de l'actualité (flux RSS publics, sans inscription)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .web import get, html_to_text, strip_tags

DEFAULT_FEEDS = {
    "fr": ["https://www.francetvinfo.fr/titres.rss", "https://www.lemonde.fr/rss/une.xml"],
    "en": ["https://feeds.bbci.co.uk/news/world/rss.xml"],
}


@dataclass
class Headline:
    title: str
    summary: str
    link: str


def parse_feed(data: bytes) -> list[Headline]:
    root = ET.fromstring(data)
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    headlines = []
    for item in items:
        title = strip_tags(item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "")
        summary = strip_tags(item.findtext("description")
                             or item.findtext("{http://www.w3.org/2005/Atom}summary") or "")
        link = item.findtext("link") or ""
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            link = atom_link.get("href", "") if atom_link is not None else ""
        if title:
            headlines.append(Headline(title, summary, link.strip()))
    return headlines


def fetch_headlines(feeds: list[str], count: int = 5) -> list[Headline]:
    for url in feeds:
        try:
            headlines = parse_feed(get(url))
        except Exception:
            continue
        if headlines:
            return headlines[:count]
    return []


def fetch_article(headline: Headline, max_chars: int = 12000) -> str:
    """Texte de l'article complet (ou au moins le résumé du flux)."""
    try:
        text = html_to_text(get(headline.link).decode("utf-8", errors="ignore"))
    except Exception:
        text = ""
    return (text or headline.summary)[:max_chars]
