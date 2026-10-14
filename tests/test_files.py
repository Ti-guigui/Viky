import os
from pathlib import Path

from viky.files import FileIndex, best_match, split_kind


def test_split_kind():
    assert split_kind("la présentation du mariage") == ("ppt", "mariage")
    assert split_kind("le PDF contrat") == ("pdf", "contrat")
    assert split_kind("le tableau budget 2026") == ("xls", "budget 2026")
    assert split_kind("budget") == (None, "budget")


def make(tmp_path, *names):
    paths = []
    for i, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        os.utime(path, (1000 + i, 1000 + i))
        paths.append(path)
    return paths


def test_best_match(tmp_path):
    files = make(tmp_path, "Mariage_Julie.pptx", "mariage-julie.pdf", "Budget 2026.xlsx",
                 "Spectacle/tour_des_cartes.pptx", "contrat.pdf")
    assert best_match("la présentation mariage", files).name == "Mariage_Julie.pptx"
    assert best_match("le pdf mariage julie", files).name == "mariage-julie.pdf"
    assert best_match("budget", files).name == "Budget 2026.xlsx"
    assert best_match("tour des cartes", files).name == "tour_des_cartes.pptx"
    assert best_match("contra", files).name == "contrat.pdf"
    assert best_match("photo de vacances", files) is None


def test_latest(tmp_path):
    files = make(tmp_path, "a.pptx", "b.pptx", "c.pdf")
    assert best_match("la dernière présentation", files).name == "b.pptx"


def test_index_walks_folders(tmp_path):
    make(tmp_path, "docs/rapport.pdf", "docs/.cache/secret.pdf", "docs/~$rapport.docx",
         "docs/notes.zip")
    index = FileIndex([tmp_path])
    assert index.find("le pdf rapport").name == "rapport.pdf"
    assert {p.name for p in index.files} == {"rapport.pdf"}
