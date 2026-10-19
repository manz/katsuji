"""Fonts written as the game's own layout: SNES tiles, 16-pixel 1bpp rows plus a width table."""

from pathlib import Path

import numpy as np
import pytest

from katsuji.atlas import Atlas, save_png
from katsuji.build import build
from katsuji.config import ConfigError, load
from katsuji.tile_fonts import (
    encode_rows16_font,
    encode_tile_font,
    pack_rows16,
    rows16_widths,
    unpack_rows16,
)
from katsuji.tiles import decode_tile
from tests.test_colours import PALETTE, colour_atlas, colour_cells


def _rows_atlas() -> Atlas:
    """Three 12x11 cells: 0 blank, 1 a 5-pixel bar on row 3, 2 a single pixel at column 11."""
    pixels = np.zeros((11, 36), dtype=np.uint8)
    pixels[3, 12:17] = 1
    pixels[0, 35] = 1
    return Atlas(pixels, 12, 11)


def test_tile_font_writes_each_cell_as_a_tile() -> None:
    data = encode_tile_font(colour_atlas(), bpp=2, first=1, count=1)
    assert decode_tile(data, 2)[0, 0] == 3


def test_tile_font_pads_to_its_size() -> None:
    assert len(encode_tile_font(colour_atlas(), bpp=2, first=0, count=2, size=64)) == 64


def test_glyphs_bigger_than_the_size_are_refused() -> None:
    with pytest.raises(ValueError, match="do not fit"):
        encode_tile_font(colour_atlas(), bpp=2, size=8)


def test_rows16_puts_the_leftmost_pixel_in_bit_15_after_the_offset() -> None:
    glyph = np.zeros((1, 12), dtype=np.uint8)
    glyph[0, 0] = 1
    assert pack_rows16(glyph, 4) == (0x0800).to_bytes(2, "little")


def test_rows16_round_trips() -> None:
    glyph = _rows_atlas().glyph(1)
    assert (unpack_rows16(pack_rows16(glyph, 4), 11, 4, 12) == glyph).all()


def test_rows16_refuses_a_glyph_past_the_row() -> None:
    with pytest.raises(ValueError, match="does not fit a 16-pixel row"):
        pack_rows16(np.zeros((1, 12), dtype=np.uint8), 5)


def test_rows16_font_lists_glyphs_from_first() -> None:
    assert len(encode_rows16_font(_rows_atlas(), 4, first=1, count=2)) == 2 * 11 * 2


def test_rows16_widths_add_the_spacing_to_drawn_glyphs_only() -> None:
    widths = rows16_widths(_rows_atlas(), spacing=1, overrides={}, first=0, count=3)
    assert (widths[0], widths[1], widths[2], widths[3], len(widths)) == (0, 6, 13, 0, 256)


def test_rows16_widths_take_overrides() -> None:
    assert rows16_widths(_rows_atlas(), 1, {0: 4, 1: -1}, count=3)[:2] == bytes([4, 5])


def test_rows16_widths_must_fit_a_byte() -> None:
    with pytest.raises(ValueError, match="fit a byte"):
        rows16_widths(_rows_atlas(), 1, {0: 300}, count=3)


def _config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "katsuji.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_build_writes_tile_and_rows16_fonts(tmp_path: Path) -> None:
    save_png(colour_cells(), tmp_path / "menu.png", PALETTE)
    save_png(_rows_atlas().pixels, tmp_path / "dialog.png")
    config = _config(
        tmp_path,
        """
[fonts.menu]
format = "tiles"
png = "menu.png"
cell = [8, 8]
bpp = 2
first = "0x01"
count = 1
output = "out/menu.dat"

[fonts.dialog]
format = "rows16"
png = "dialog.png"
cell = [12, 11]
first = "0x01"
count = 2
x-offset = 4
spacing = 1
size = 64
widths = { "0x00" = 3 }
output = "out/dialog.dat"
widths-output = "out/widths.dat"
""",
    )
    written = build(load(config))
    out = tmp_path / "out"
    assert {p.name for p in written} == {"menu.dat", "dialog.dat", "widths.dat"}
    assert (len((out / "menu.dat").read_bytes()), len((out / "dialog.dat").read_bytes())) == (16, 64)
    assert (out / "widths.dat").read_bytes()[:3] == bytes([3, 6, 13])


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('format = "bitmap"', "format 'bitmap' is not one of"),
        ('format = "rows16"', "needs `widths-output`"),
        ('format = "tiles"\nkerning = { "tt" = 2 }', r"unknown key\(s\) \['kerning'\]"),
        ('format = "tiles"\nfirst = "zero"', "'zero' is not a code"),
    ],
)
def test_tile_font_config_errors(tmp_path: Path, text: str, message: str) -> None:
    config = _config(tmp_path, f'[fonts.f]\npng = "f.png"\noutput = "f.dat"\n{text}\n')
    with pytest.raises(ConfigError, match=message):
        load(config)


def test_strings_need_a_vwf_font(tmp_path: Path) -> None:
    save_png(colour_cells(), tmp_path / "menu.png", PALETTE)
    config = _config(
        tmp_path,
        """
[fonts.menu]
format = "tiles"
png = "menu.png"
cell = [8, 8]
output = "menu.dat"

[strings.items]
font = "menu"
texts = ["a"]
blob = "b.dat"
index = "b.idx"
""",
    )
    with pytest.raises(ConfigError, match="is not a 'vwf' font"):
        build(load(config))
