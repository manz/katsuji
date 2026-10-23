"""`TableMeasure`: script text measured through its table and the font, tags at their own widths."""

from pathlib import Path

import pytest

from katsuji.formats import VwfFont
from katsuji.layout import TableMeasure, TextLayout
from katsuji.script import Table
from katsuji.typeset import Markup
from katsuji.wrap import Controls, Wrapper

A, B, SPACE = 0x10, 0x11, 0xFF


@pytest.fixture
def table(tmp_path: Path) -> Table:
    path = tmp_path / "t.tbl"
    path.write_text("10=a\n11=b\nFF= \n", encoding="utf-8")
    return Table(str(path))


@pytest.fixture
def wrapper() -> Wrapper:
    """Every glyph 3 pixels wide, the space 2, gap 1: a letter advances 4, a space 3."""
    widths = [3] * 256
    widths[SPACE] = 2
    return Wrapper([VwfFont(1, [b"\x00"] * 256, widths)], Controls(space=SPACE))


def test_text_measures_as_its_codes(table: Table, wrapper: Wrapper) -> None:
    assert TableMeasure(table, wrapper)("ab a") == wrapper.measure(bytes([A, B, SPACE, A]))


def test_a_tag_measures_its_width(table: Table, wrapper: Wrapper) -> None:
    measure = TableMeasure(table, wrapper, tag_widths={r"\[name:\d\]": 48})
    assert measure("a[name:1]b") == 4 + 48 + 4


def test_an_unknown_tag_measures_nothing(table: Table, wrapper: Wrapper) -> None:
    assert TableMeasure(table, wrapper)("a[wait]b") == 8


def test_tags_follow_the_markup(table: Table, wrapper: Wrapper) -> None:
    measure = TableMeasure(table, wrapper, markup=Markup(tag=r"<[^>]*>"), tag_widths={"<n>": 10})
    assert measure("a<n>") == 14


def test_drives_a_text_layout(table: Table, wrapper: Wrapper) -> None:
    """ "ab ab" measures 19 pixels, "ab ab ab" 30: a 20-pixel window takes two lines, a 30-pixel one a single line."""
    measure = TableMeasure(table, wrapper)
    assert [TextLayout(measure, width).reflow("ab ab ab").count("\n") for width in (20, 30)] == [1, 0]
