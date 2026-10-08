"""ff4's kerning results, kept as goldens on its dialog font."""

import numpy as np
import pytest
from script import Table

from katsuji import Atlas, find_kerning, pair_kerning
from katsuji.kerning import collides, touches


def _pair(table: Table, text: str) -> tuple[int, int]:
    codes = table.to_bytes(text)
    return codes[0], codes[1]


@pytest.mark.parametrize(("text", "expected"), [("ïe", -1), ("re", -1), ("ce", 0)])
def test_ff4_kerning_goldens(dialog_atlas: Atlas, dialog_table: Table, text: str, expected: int) -> None:
    assert pair_kerning(dialog_atlas, *_pair(dialog_table, text)) == expected


@pytest.mark.parametrize("text", ["Ta", "va"])
def test_classic_pairs_tighten(dialog_atlas: Atlas, dialog_table: Table, text: str) -> None:
    assert pair_kerning(dialog_atlas, *_pair(dialog_table, text)) < 1


def test_default_zero_tries_overlap(dialog_atlas: Atlas, dialog_table: Table) -> None:
    assert pair_kerning(dialog_atlas, *_pair(dialog_table, "fo"), default=0) != 0


def test_find_kerning_keeps_only_tightening_pairs(dialog_atlas: Atlas, dialog_table: Table) -> None:
    ie, ce = _pair(dialog_table, "ïe"), _pair(dialog_table, "ce")
    assert find_kerning(dialog_atlas, [ie, ce]) == {ie: 1}


def test_touches_counts_diagonal_and_side_contacts() -> None:
    left = np.array([[1], [0]], dtype=np.uint8)
    right = np.array([[0], [1]], dtype=np.uint8)
    assert touches(left, right, 1) == (1, 0)


def test_side_by_side_ink_is_an_orthogonal_touch() -> None:
    glyph = np.array([[1]], dtype=np.uint8)
    assert touches(glyph, glyph, 1) == (0, 1)


def test_collides_on_shared_ink() -> None:
    glyph = np.array([[1, 1]], dtype=np.uint8)
    assert collides(glyph, glyph, 1)


def test_overlap_search_runs_when_the_gap_cannot_close() -> None:
    """`#.#` then `#`: one pixel in is a side touch, two collides, so default 0 stays 0."""
    pixels = np.zeros((1, 16), dtype=np.uint8)
    pixels[0, [0, 2, 8]] = 1
    atlas = Atlas(pixels, cell_width=8, cell_height=1)
    assert pair_kerning(atlas, 0, 1, default=0) == 0


def test_overlap_search_finds_a_hole_in_the_left_glyph() -> None:
    """Left `...#.` over `#...#`, right a single pixel on row 1.

    Closing the gap collides at once, so the overlap search runs: the pixel
    drops into column 2, touching only `(0, 3)` diagonally, four pixels in.
    """
    pixels = np.zeros((2, 16), dtype=np.uint8)
    pixels[0, 3] = 1
    pixels[1, [0, 4]] = 1
    pixels[1, 8] = 1
    atlas = Atlas(pixels, cell_width=8, cell_height=2)
    assert pair_kerning(atlas, 0, 1, default=0) == -4
