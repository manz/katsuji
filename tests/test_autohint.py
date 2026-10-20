"""Auto mode: text set straight from a font PNG, colours kept, as ff4's banner `--autohint` did."""

from pathlib import Path

import numpy as np
from PIL import Image
from script import Table

from katsuji import Atlas, autohint, render_colours
from katsuji.cli import main
from katsuji.formats import VwfFont

LEVELS = (0, 85, 170, 255)


def _bar(colour: int, width: int) -> np.ndarray:
    """An 8x8 cell: a full-height bar of `colour`, then a shadow column of colour 1."""
    cell = np.zeros((8, 8), dtype=np.uint8)
    cell[:, :width] = colour
    cell[:, width] = 1
    return cell


def _grey_png(path: Path) -> Path:
    cells = np.concatenate([np.zeros((8, 8), np.uint8), _bar(3, 2), _bar(2, 3)], axis=1)
    Image.fromarray(np.array(LEVELS, np.uint8)[cells], mode="L").save(path)
    return path


def test_a_grey_png_keeps_its_levels_as_colours(tmp_path: Path) -> None:
    atlas = Atlas.open(_grey_png(tmp_path / "f.png"), 8, 8)
    assert (atlas.glyph_colours(1)[0, 0], atlas.glyph_colours(1)[0, 2]) == (3, 1)


def test_a_grey_png_with_many_levels_has_no_colours(tmp_path: Path) -> None:
    Image.fromarray(np.arange(64, dtype=np.uint8).reshape(8, 8) * 4, mode="L").save(tmp_path / "g.png")
    assert Atlas.open(tmp_path / "g.png", 8, 8).colours is None


def test_render_colours_keeps_the_shadow(tmp_path: Path) -> None:
    atlas = Atlas.open(_grey_png(tmp_path / "f.png"), 8, 8)
    pixels = render_colours(VwfFont.from_atlas(atlas), atlas, [1])
    assert pixels[0].tolist() == [3, 3, 1]


def test_render_colours_lays_out_as_render(tmp_path: Path) -> None:
    atlas = Atlas.open(_grey_png(tmp_path / "f.png"), 8, 8)
    pixels = render_colours(VwfFont.from_atlas(atlas), atlas, [1, 2])
    assert pixels[0].tolist() == [3, 3, 1, 0, 2, 2, 2, 1]


def test_autohint_kerns_on_the_glyphs(dialog_atlas: Atlas, dialog_table: Table) -> None:
    codes = list(dialog_table.to_bytes("Ta"))
    unkerned = render_colours(VwfFont.from_atlas(dialog_atlas), dialog_atlas, codes)
    assert autohint(dialog_atlas, codes).shape[1] < unkerned.shape[1]


def test_banner_auto_saves_a_colour_png(tmp_path: Path) -> None:
    table = tmp_path / "t.tbl"
    table.write_text("01=a\n02=b\n", encoding="utf-8")
    png = _grey_png(tmp_path / "f.png")
    assert (
        main(
            [
                "banner",
                "ab",
                "--table",
                str(table),
                "--font",
                str(png),
                "--auto",
                "--cell",
                "8x8",
                "--png",
                str(tmp_path / "o.png"),
            ]
        )
        == 0
    )
    assert np.array(Image.open(tmp_path / "o.png"))[0].tolist() == [3, 3, 1, 0, 2, 2, 2, 1]
