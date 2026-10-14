import pytest

from viky.numbers import parse_cell, parse_number, parse_value


@pytest.mark.parametrize("text, value", [
    ("12", 12), ("douze", 12), ("vingt et un", 21), ("dix sept", 17), ("soixante dix", 70),
    ("soixante dix sept", 77), ("quatre vingt", 80), ("quatre vingt dix neuf", 99),
    ("deux cent cinquante", 250), ("mille deux cents", 1200), ("troisieme", 3), ("3e", 3),
    ("numero cinq", 5), ("twenty one", 21), ("third", 3), ("one hundred", 100),
])
def test_parse_number(text, value):
    assert parse_number(text) == value


def test_not_a_number():
    assert parse_number("bonjour") is None
    assert parse_number("") is None


@pytest.mark.parametrize("text, value", [
    ("cinq cents", 500), ("douze virgule cinq", 12.5), ("12,5", 12.5), ("moins trois", -3),
    ("payé", "payé"), ("jean dupont", "jean dupont"),
])
def test_parse_value(text, value):
    assert parse_value(text) == value


@pytest.mark.parametrize("text, cell", [
    ("b3", "B3"), ("b 3", "B3"), ("b trois", "B3"), ("be trois", "B3"), ("aa 12", "AA12"),
    ("a a douze", "AA12"), ("c vingt", "C20"), ("hache cinq", "H5"),
])
def test_parse_cell(text, cell):
    assert parse_cell(text) == cell


def test_bad_cell():
    assert parse_cell("bonjour") is None
    assert parse_cell("b") is None
