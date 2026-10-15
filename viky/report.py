"""Enregistre les rapports de recherche en pages web lisibles (et projetables)."""

from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from .actions import user_dir
from .text import normalize

_STYLE = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 24px;
line-height:1.6;color:#1d1d1f;background:#fafafa;font-size:20px}
h1{font-size:2em;color:#3b2a8f}h2{color:#3b2a8f;border-bottom:2px solid #e3defa;padding-bottom:4px}
a{color:#5b3fd1}li{margin:4px 0}.date{color:#777}
"""


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return re.sub(r"(?<![\"=>])(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)


def markdown_to_html(markdown: str) -> str:
    out: list[str] = []
    in_list = False
    for line in markdown.splitlines():
        stripped = line.strip()
        bullet = re.match(r"^([-*•]|\d+\.)\s+(.*)", stripped)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(bullet.group(2))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,4})\s+(.*)", stripped)
        if heading:
            level = min(len(heading.group(1)) + 1, 4)
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif stripped:
            out.append(f"<p>{_inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def save_report(topic: str, markdown: str, folder: Path | None = None) -> Path:
    folder = folder or user_dir("Documents") / "Viky" / "Recherches"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    slug = re.sub(r"\s+", "-", normalize(topic))[:60] or "recherche"
    path = folder / f"{now:%Y-%m-%d_%H%M}_{slug}.html"
    title = html.escape(topic[:1].upper() + topic[1:])
    path.write_text(
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{title}</title>"
        f"<style>{_STYLE}</style></head><body><h1>{title}</h1>"
        f"<p class='date'>Recherche de Viky — {now:%d/%m/%Y %H:%M}</p>"
        f"{markdown_to_html(markdown)}</body></html>",
        encoding="utf-8",
    )
    return path
