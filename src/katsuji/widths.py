"""Advance widths: measured from the ink, adjusted by per-glyph overrides."""

from __future__ import annotations

from collections.abc import Mapping

from katsuji.atlas import Atlas


def measured_widths(atlas: Atlas, count: int = 256) -> list[int]:
    """The ink width of the first `count` glyphs."""
    return [atlas.ink_width(index) for index in range(count)]


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
