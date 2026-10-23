"""Static rendering: text drawn at build time exactly as the a816 runtime draws it.

The runtime ORs all 8 bits of each glyph row in at the pen, then advances by
`width + gap - kerning`. A glyph whose width is set narrower than its ink
therefore still shows that ink, overlapping what follows; this module does
the same so pre-rendered and runtime pixels match. (ff4's Python preview
clipped glyphs to their width instead.)
"""

from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise

import numpy as np

from katsuji.atlas import Atlas, Pixels
from katsuji.formats import VwfFont
from katsuji.kerning import find_kerning


def advances(font: VwfFont, codes: Sequence[int], gap: int = 1) -> list[int]:
    """Pen position of each glyph, then the total width."""
    pen = 0
    positions = []
    for index, code in enumerate(codes):
        positions.append(pen)
        pen += font.widths[code]
        if index + 1 < len(codes):
            pen += gap - font.kerning.get((code, codes[index + 1]), 0)
    return [*positions, pen]


def measure(font: VwfFont, codes: Sequence[int], gap: int = 1) -> int:
    """Pixel width of `codes` set with `font`."""
    return advances(font, codes, gap)[-1]


def render(font: VwfFont, codes: Sequence[int], gap: int = 1) -> Pixels:
    """The 0/1 pixels of `codes` set with `font`, `font.height` rows tall.

    The canvas is as wide as the text's advance, or wider when the last glyph's
    ink runs past it.
    """
    positions = advances(font, codes, gap)
    width = max([positions[-1]] + [pen + 8 for pen in positions[:-1]]) if codes else 0
    canvas = np.zeros((font.height, width), dtype=np.uint8)
    for pen, code in zip(positions, codes, strict=False):
        glyph = font.glyph(code)
        canvas[:, pen : pen + 8] |= glyph[:, : max(0, min(8, width - pen))]
    return canvas[:, : max(positions[-1], _ink_extent(canvas))]


def render_colours(
    font: VwfFont, atlas: Atlas, codes: Sequence[int], gap: int = 1, ink: Iterable[int] | None = None
) -> Pixels:
    """`render`'s layout drawn with `atlas`'s colour indices: a later glyph's pixels cover an earlier one's, except
    that `ink` colours are never covered by the others (a glyph's shadow stays under its neighbour's letter)."""
    inked = None if ink is None else list(ink)
    positions = advances(font, codes, gap)
    width = max(
        [positions[-1]] + [pen + font.glyph(code).shape[1] for pen, code in zip(positions, codes, strict=False)]
    )
    canvas = np.zeros((font.height, width if codes else 0), dtype=np.uint8)
    for pen, code in zip(positions, codes, strict=False):
        cell = atlas.glyph_colours(code)[: font.height, : font.glyph(code).shape[1]]
        view = canvas[:, pen : pen + cell.shape[1]]
        drawn = cell != 0
        if inked is not None:
            drawn &= np.isin(cell, inked) | ~np.isin(view, inked)
        view[drawn] = cell[drawn]
    return canvas[:, : max(positions[-1], _ink_extent(canvas))]


def autohint(
    atlas: Atlas,
    codes: Sequence[int],
    gap: int = 1,
    default: int = 1,
    ink: Iterable[int] | None = None,
    widths: Mapping[int, int] | None = None,
    avoid: Iterable[int] = (),
) -> Pixels:
    """`codes` set straight from `atlas`, as ff4's banner `--autohint` did: widths measured from the ink and each
    pair kerned on the glyphs (`pair_kerning`), no font file. Colour indices, so a shadowed font keeps its shadow.

    With `ink`, only those colours are measured and kerned (`Atlas.ink_only`): the shadow is drawn in the gap and
    may tuck under the next glyph, whose ink covers it. `widths` overrides measured widths as `[fonts.x] widths`
    does in katsuji.toml (positive sets, negative trims): a space has no ink to measure. The gap lands on both
    sides of a space, so N pixels between words takes a width of N - 2 * gap. Pairs touching an `avoid` code keep
    their gap."""
    inked = None if ink is None else list(ink)
    metrics = atlas if inked is None else atlas.ink_only(inked)
    kerning = find_kerning(metrics, set(pairwise(codes)), default, avoid)
    font = VwfFont.from_atlas(metrics, width_overrides=widths, kerning=kerning)
    return render_colours(font, atlas, codes, gap, inked)


def _ink_extent(canvas: Pixels) -> int:
    columns = np.flatnonzero(canvas.any(axis=0))
    return int(columns[-1]) + 1 if columns.size else 0


def to_ascii(pixels: Pixels, ink: str = "#", paper: str = ".") -> str:
    """A text picture of `pixels`, one line per row."""
    return "\n".join("".join(ink if value else paper for value in row) for row in pixels)
