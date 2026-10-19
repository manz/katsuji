"""Palettized atlases: fonts drawn in more than ink and paper keep their colour indices and palette."""

from pathlib import Path

import numpy as np

from katsuji.atlas import Atlas, Pixels, save_png
from katsuji.cli import main
from katsuji.remap import remap

PALETTE = (0, 0, 0, 85, 85, 85, 170, 170, 170, 255, 255, 255)


def colour_cells() -> Pixels:
    """Four 8x8 cells of colour indices; cell 1 has colour 3 at (0, 0) and colour 2 at (7, 7)."""
    colours = np.zeros((8, 32), dtype=np.uint8)
    colours[0, 8] = 3
    colours[7, 15] = 2
    return colours


def colour_atlas() -> Atlas:
    colours = colour_cells()
    return Atlas((colours != 0).astype(np.uint8), 8, 8, colours=colours, palette=PALETTE)


def test_a_palettized_png_keeps_its_colours(tmp_path: Path) -> None:
    save_png(colour_cells(), tmp_path / "f.png", PALETTE)
    atlas = Atlas.open(tmp_path / "f.png", 8, 8)
    assert atlas.palette is not None
    assert (atlas.glyph_colours(1)[0, 0], atlas.glyph_colours(1)[7, 7], atlas.palette[:12]) == (3, 2, PALETTE)


def test_without_a_palette_colours_are_the_ink() -> None:
    pixels = np.zeros((8, 16), dtype=np.uint8)
    pixels[3, 8] = 1
    assert Atlas(pixels, 8, 8).glyph_colours(1)[3, 0] == 1


def test_remap_keeps_colours_and_palette() -> None:
    remapped = remap(colour_atlas(), {"a": 1}, {"a": 0x20})
    assert (remapped.pixels[2 * 8, 0], remapped.palette) == (3, PALETTE)


def test_cli_remap_writes_the_palette(tmp_path: Path) -> None:
    save_png(colour_cells(), tmp_path / "menu.png", PALETTE)
    (tmp_path / "from.tbl").write_text("01=a\n", encoding="utf-8")
    (tmp_path / "to.tbl").write_text("20=a\n", encoding="utf-8")
    out = tmp_path / "out.png"
    args = ["remap", str(tmp_path / "menu.png"), "--table", str(tmp_path / "from.tbl"), "--cell", "8x8"]
    assert main([*args, "--to", str(tmp_path / "to.tbl"), "-o", str(out)]) == 0
    moved = Atlas.open(out, 8, 8)
    assert moved.palette is not None
    assert (moved.glyph_colours(0x20)[0, 0], moved.palette[:12]) == (3, PALETTE)
