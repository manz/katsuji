"""Pair kerning found by collision: how far a glyph can tuck under the previous one.

The rule (ff4's): glyphs never overlap or touch side by side; one diagonal
touch is the target, no touch is acceptable. A kerning is the number of
pixels removed from the gap after the left glyph, the value the assembly
subtracts from the advance and the byte a font file stores.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from katsuji.atlas import Atlas, Pixels, ink_rows, ink_width

_DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_ORTHOGONALS = ((0, 1), (0, -1), (1, 0), (-1, 0))


def _place(left: Pixels, right: Pixels, start: int) -> tuple[Pixels, Pixels]:
    """Ink and owner (1 = left, 2 = right) of `right` drawn at column `start` over `left`."""
    height = left.shape[0]
    width = max(left.shape[1], start + right.shape[1])
    ink = np.zeros((height, width), dtype=np.uint8)
    owner = np.zeros((height, width), dtype=np.uint8)
    ink[:, : left.shape[1]] |= left
    owner[:, : left.shape[1]][left != 0] = 1
    for row, column in zip(*np.nonzero(right), strict=True):
        if 0 <= start + column < width:
            ink[row, start + column] = 1
            owner[row, start + column] = 2
    return ink, owner


def touches(left: Pixels, right: Pixels, start: int) -> tuple[int, int]:
    """Diagonal and orthogonal pixel contacts between `left` and `right` placed at `start`."""
    ink, owner = _place(left, right, start)
    height, width = ink.shape
    found: dict[tuple[tuple[int, int], ...], set[tuple[tuple[int, int], tuple[int, int]]]] = {
        _DIAGONALS: set(),
        _ORTHOGONALS: set(),
    }
    for row, column in zip(*np.nonzero(ink), strict=True):
        for directions, pairs in found.items():
            for dr, dc in directions:
                r, c = row + dr, column + dc
                if 0 <= r < height and 0 <= c < width and ink[r, c] and owner[r, c] != owner[row, column]:
                    a, b = (int(row), int(column)), (int(r), int(c))
                    pairs.add((min(a, b), max(a, b)))
    return len(found[_DIAGONALS]), len(found[_ORTHOGONALS])


def collides(left: Pixels, right: Pixels, start: int) -> bool:
    """Whether `right` at column `start` puts ink on ink of `left`."""
    for column in range(right.shape[1]):
        position = start + column
        if 0 <= position < left.shape[1] and np.any(left[:, position] & right[:, column]):
            return True
    return False


def pair_kerning(atlas: Atlas, left: int, right: int, default: int = 1) -> int:
    """The tightest spacing adjustment for glyph `right` after `left`.

    The return value is ff4's `compute_kerning` result: the right glyph starts
    `width(left) + value + 1` columns in, so `-1` means one pixel tighter than
    the 1-pixel gap. With `default=0`, overlapping placements are tried too.
    """
    left_cell = atlas.glyph(left)
    right_cell = atlas.glyph(right)
    left_width = ink_width(left_cell)
    left_glyph = left_cell[:, :left_width]
    right_glyph = right_cell[:, : ink_width(right_cell)]
    top = max(ink_rows(left_glyph)[0], ink_rows(right_glyph)[0])
    bottom = min(ink_rows(left_glyph)[1], ink_rows(right_glyph)[1])
    share_rows = top <= bottom

    best = default
    for reduction in range(1, max(1, default) + left_width + 1):
        value = default - reduction
        start = left_width + value + 1
        if share_rows and collides(left_glyph, right_glyph, start):
            break
        diagonal, orthogonal = touches(left_glyph, right_glyph, start)
        if orthogonal:
            continue
        if diagonal == 1:
            return value
        if diagonal == 0:
            best = value

    if default == 0 and best == default:
        for overlap in range(1, left_width):
            value = -overlap
            start = left_width + value + 1
            if share_rows and collides(left_glyph, right_glyph, start):
                continue
            diagonal, orthogonal = touches(left_glyph, right_glyph, start)
            if orthogonal:
                continue
            if diagonal == 1:
                return value
            if diagonal == 0:
                best = value
    return best


def find_kerning(atlas: Atlas, pairs: Iterable[tuple[int, int]], default: int = 1) -> dict[tuple[int, int], int]:
    """Kerning bytes for the candidate `pairs` that tighten, as `{(left, right): pixels}`.

    Only pairs whose `pair_kerning` is negative are kept, stored as the
    positive number of pixels removed, ready for `VwfFont.kerning`.
    """
    found: dict[tuple[int, int], int] = {}
    for left, right in pairs:
        value = pair_kerning(atlas, left, right, default)
        if value < 0:
            found[(left, right)] = -value
    return found
