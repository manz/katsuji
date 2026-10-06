"""katsuji rebuilds ff4's five VWF fonts byte for byte.

The fixtures are ff4's source PNGs and text tables, and the `.dat` files its
build produced. The candidate pairs, width overrides and the hand-tuned `tt`
pair are ff4's build configuration, kept here as data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from script import Table

from katsuji import Atlas, VwfFont, find_kerning

FF4 = Path(__file__).parent / "fixtures" / "ff4"

_LETTERS = ["T", "V", "F", "P", "A", "W", "Y", "L", "v", "t", "f", "r"]
_VOWELS = ["a", "e", "i", "o", "u", "é", "à", "â", "è", "ê", "ï", "îr"]
_DIALOG_CANDIDATES = (
    [letter + vowel for letter in _LETTERS for vowel in _VOWELS]
    + [vowel + tail for vowel in [*_VOWELS, "n"] for tail in ("j", "g", "y", "t", "f")]
    + ["rn", "fi", "fl", "ff", "tt", "ll"]
    + ["ît", "aî", "va", "ïe", "în", "bî", "îm", "Îl", "aï", "ïm"]
)
_MENU_CANDIDATES = [
    "Ya", "Pa", "PoFa", "Fe", "Fo", "Fu", "Ta", "Te", "To", "Tu", "Tr", "Ts", "ra", "re", "ro", "Aï", "ïe", "aî",
    "ît", "pa", "at", "ta", "te", "nt", "fa", "fe", "fo", "fu", "fi", "st", "va",
]  # fmt: skip


def _pairs(table: Table, texts: list[str]) -> list[tuple[int, int]]:
    """The candidates that encode to exactly two codes (ff4 skips the others)."""
    codes = (table.to_bytes(text) for text in texts)
    return [(c[0], c[1]) for c in codes if len(c) == 2]


def _dialog_font(png: str, space: int) -> bytes:
    table = Table(str(FF4 / "ff4fr.tbl"))
    atlas = Atlas.open(FF4 / png, cell_height=16)
    kerning = find_kerning(atlas, _pairs(table, _DIALOG_CANDIDATES))
    tt = table.to_bytes("tt")
    kerning[(tt[0], tt[1])] = 2  # hand-tuned: two pixels tighter
    overrides = {0xFF: space, 0xFD: 1, 0xFE: 2, 0xA0: -1}
    return VwfFont.from_atlas(atlas, overrides, kerning).encode()


@pytest.mark.parametrize(
    ("png", "dat", "space"),
    [
        ("vwf.png", "font.dat", 3),
        ("bold_vwf.png", "bold_font.dat", 5),
        ("wicked_vwf.png", "wicked_font.dat", 5),
        ("book_vwf.png", "book_font.dat", 5),
    ],
)
def test_dialog_fonts_match_ff4(png: str, dat: str, space: int) -> None:
    assert _dialog_font(png, space) == (FF4 / dat).read_bytes()


def test_menu_font_matches_ff4() -> None:
    table = Table(str(FF4 / "ff4_menus.tbl"))
    atlas = Atlas.open(FF4 / "8x8vwf.png", cell_height=8)
    kerning = find_kerning(atlas, _pairs(table, _MENU_CANDIDATES))
    font = VwfFont.from_atlas(atlas, {0xFF: 3}, kerning)
    assert font.encode() == (FF4 / "menu_font.dat").read_bytes()


@pytest.mark.parametrize("dat", ["font.dat", "bold_font.dat", "wicked_font.dat", "book_font.dat", "menu_font.dat"])
def test_ff4_fonts_round_trip(dat: str) -> None:
    data = (FF4 / dat).read_bytes()
    assert VwfFont.decode(data).encode() == data
