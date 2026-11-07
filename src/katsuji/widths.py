"""Advance widths: measured from the ink, adjusted by per-glyph overrides."""

from collections.abc import Mapping

from katsuji.atlas import Atlas
from katsuji.fonts import Slant


def measured_widths(atlas: Atlas, count: int = 256) -> list[int]:
    """The ink width of the first `count` glyphs."""
    return [atlas.ink_width(index) for index in range(count)]


def upright_widths(atlas: Atlas, slant: Slant, count: int = 256) -> list[int]:
    """The ink width of the first `count` glyphs set upright: each row's ink moved back by `slant`'s lean, so a
    slanted glyph advances as its upright self, its lean overhanging the next."""
    widths = []
    for index in range(count):
        rows, columns = atlas.glyph(index).nonzero()
        widths.append(
            max(int(column) - slant.lean(int(row)) for row, column in zip(rows, columns, strict=True)) + 1
            if rows.size
            else 0
        )
    return widths


def apply_overrides(widths: list[int], overrides: Mapping[int, int]) -> list[int]:
    """Widths with `overrides` applied, ff4's convention: a negative value is
    added to the measured width (`-1` trims a column), a positive value
    replaces it (`3` for a space), and 0 leaves it measured."""
    adjusted = list(widths)
    for index, override in overrides.items():
        if override < 0:
            adjusted[index] += override
        elif override > 0:
            adjusted[index] = override
    return adjusted
