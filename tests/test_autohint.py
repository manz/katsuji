"""Auto mode: text set straight from a font PNG, colours kept, as ff4's banner `--autohint` did."""

from pathlib import Path

import numpy as np
from PIL import Image

from katsuji import Atlas, autohint, render_colours
from katsuji.cli import main
from katsuji.formats import VwfFont
from katsuji.script import Table

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


def _ink_png(path: Path) -> Path:
    """Glyph 1: ink (3) in columns 0-1, shadow (1) in column 2; glyph 2: ink in columns 0-2, shadow in 3."""
    cells = np.concatenate([np.zeros((8, 8), np.uint8), _bar(3, 2), _bar(3, 3)], axis=1)
    Image.fromarray(np.array(LEVELS, np.uint8)[cells], mode="L").save(path)
    return path


def test_ink_only_leaves_the_shadow_out_of_the_width(tmp_path: Path) -> None:
    atlas = Atlas.open(_ink_png(tmp_path / "f.png"), 8, 8)
    assert (atlas.ink_width(1), atlas.ink_only([3]).ink_width(1)) == (3, 2)


def test_ink_only_keeps_the_colours(tmp_path: Path) -> None:
    atlas = Atlas.open(_ink_png(tmp_path / "f.png"), 8, 8)
    assert atlas.ink_only([3]).glyph_colours(1)[0].tolist() == atlas.glyph_colours(1)[0].tolist()


def test_autohint_on_ink_puts_the_shadow_in_the_gap(tmp_path: Path) -> None:
    atlas = Atlas.open(_ink_png(tmp_path / "f.png"), 8, 8)
    assert autohint(atlas, [1, 2], ink=[3])[0].tolist() == [3, 3, 1, 3, 3, 3, 1]


def test_ink_is_not_covered_by_a_shadow() -> None:
    font = VwfFont(1, [bytes([0xC0]), bytes([0x80])], [1, 1])
    colours = np.array([[3, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]], dtype=np.uint8)
    atlas = Atlas((colours != 0).astype(np.uint8), 8, 1, colours=colours)
    assert render_colours(font, atlas, [0, 1], gap=0, ink=[3])[0].tolist()[:2] == [3, 1]


def test_banner_auto_measures_on_the_ink_colours(tmp_path: Path) -> None:
    table = tmp_path / "t.tbl"
    table.write_text("01=a\n02=b\n", encoding="utf-8")
    png, out = _ink_png(tmp_path / "f.png"), tmp_path / "o.png"
    args = ["banner", "ab", "--table", str(table), "--font", str(png), "--auto", "--cell", "8x8", "--ink", "3"]
    assert main([*args, "--png", str(out)]) == 0
    assert np.array(Image.open(out))[0].tolist() == [3, 3, 1, 3, 3, 3, 1]
