from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from katsuji.atlas import Atlas, ink_rows, ink_width, save_png


def _grid_atlas() -> Atlas:
    """Two 3x2 cells behind a 1-pixel grid: cell 0 inked at (0, 0), cell 1 at (1, 2)."""
    pixels = np.ones((4, 9), dtype=np.uint8)  # grid lines everywhere
    pixels[1:3, 1:4] = 0
    pixels[1:3, 5:8] = 0
    pixels[1, 1] = 1
    pixels[2, 7] = 1
    return Atlas(pixels, cell_width=3, cell_height=2, grid=True)


def test_grid_cells_skip_the_lines() -> None:
    atlas = _grid_atlas()
    assert atlas.glyph(1).tolist() == [[0, 0, 0], [0, 0, 1]]


def test_grid_atlas_counts_its_cells() -> None:
    assert len(_grid_atlas()) == 2


def test_plain_cells_are_packed_edge_to_edge() -> None:
    pixels = np.zeros((2, 6), dtype=np.uint8)
    pixels[0, 4] = 1
    atlas = Atlas(pixels, cell_width=3, cell_height=2)
    assert atlas.glyph(1).tolist() == [[0, 1, 0], [0, 0, 0]]


def test_without_grid_packs_the_cells() -> None:
    assert _grid_atlas().without_grid().tolist() == [[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1]]


def test_ink_width_is_the_rightmost_ink_column() -> None:
    assert ink_width(np.array([[1, 1, 0, 0], [1, 1, 1, 0]], dtype=np.uint8)) == 3


def test_a_blank_glyph_has_no_width() -> None:
    assert ink_width(np.zeros((2, 4), dtype=np.uint8)) == 0


def test_ink_rows_of_a_blank_glyph_span_the_cell() -> None:
    assert ink_rows(np.zeros((5, 4), dtype=np.uint8)) == (0, 4)


def test_open_treats_any_non_zero_pixel_as_ink(tmp_path: Path) -> None:
    Image.fromarray(np.array([[0, 255], [7, 0]], dtype=np.uint8), mode="L").save(tmp_path / "f.png")
    atlas = Atlas.open(tmp_path / "f.png", cell_width=2, cell_height=2)
    assert atlas.glyph(0).tolist() == [[0, 1], [1, 0]]


def test_save_png_writes_black_ink(tmp_path: Path) -> None:
    save_png(np.array([[1, 0]], dtype=np.uint8), tmp_path / "out.png")
    assert np.array(Image.open(tmp_path / "out.png")).tolist() == [[0, 255]]


def test_open_reads_the_first_channel_of_a_colour_png(tmp_path: Path) -> None:
    rgb = np.zeros((1, 2, 3), dtype=np.uint8)
    rgb[0, 1, 0] = 255
    Image.fromarray(rgb, mode="RGB").save(tmp_path / "f.png")
    assert Atlas.open(tmp_path / "f.png", cell_width=2, cell_height=1).glyph(0).tolist() == [[0, 1]]
