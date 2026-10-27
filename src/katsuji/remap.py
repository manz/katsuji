"""A font moved from one game's text table to another's: the same glyphs, at the codes the other table gives them."""

import itertools
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from katsuji.atlas import Atlas, Pixels, ink_width

COLUMNS = 16
GLYPHS = 256

Span = tuple[int, ...]
"""The codes one glyph is drawn across, left to right: `(0x41,)`, or `(0xA0, 0xA1)` for a glyph wider than a
cell (ff4's `A0A1=œ`, bl's two-cell icons)."""
Target = Mapping[int, str] | Mapping[Span, str]
"""A game's table as `remap` takes it: by code, or by span as `table_texts` reads it."""


def table_texts(path: Path | str) -> dict[Span, str]:
    """The text of every code of a `.tbl` (`XX=text`), and of every run of codes one character is drawn across
    (`A0A1=œ`); a text may have several. A run whose text is several characters is a control or a DTE pair, not
    a glyph, and is left out."""
    texts: dict[Span, str] = {}
    for span, text in _entries(Path(path)):
        texts.setdefault(span, text)
    return texts


def table_codes(path: Path | str) -> dict[str, Span]:
    """`table_texts` by text; the first codes a text has win."""
    codes: dict[str, Span] = {}
    for span, text in _entries(Path(path)):
        codes.setdefault(text, span)
    return codes


def _entries(path: Path) -> Iterator[tuple[Span, str]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, text = line.partition("=")
        if not sep or not text or len(key) % 2 or (len(key) > 2 and len(text) != 1):
            continue
        try:
            yield tuple(bytes.fromhex(key)), text
        except ValueError:
            continue


@dataclass(frozen=True)
class Remapped:
    pixels: Pixels
    """The new atlas: 16 cells per row, 256 cells, each glyph at its target code. Colour indices when the source
    PNG is palettized, else ink (1) and paper (0)."""
    missing: list[str]
    """One-code texts the target table has that the source font doesn't draw."""
    palette: tuple[int, ...] | None = None
    """The source PNG's palette, to write the new one with."""
    joins: dict[int, int] = field(default_factory=dict)
    """The width of each code a glyph continues past (all of a span but its last): the cut, less the 1-pixel gap
    the engine adds, so the next cell's pixels follow on."""


def remap(atlas: Atlas, source: Mapping[str, Span], target: Target, wide: Mapping[str, Span] | None = None) -> Remapped:
    """Each code of `target` gets the source glyph that `source` gives its text, every code a text has; the
    other cells stay blank. A glyph is cut across the codes of a span, from `wide` when it draws the text
    wider; a span whose text the source lacks is left blank, not missing (a game's two-byte kanji codes are
    not cells)."""
    width, height = atlas.cell_width, atlas.cell_height
    pixels = np.zeros((GLYPHS // COLUMNS * height, COLUMNS * width), dtype=np.uint8)
    missing: list[str] = []
    joins: dict[int, int] = {}
    for span, text in sorted((_span(key), text) for key, text in target.items()):
        if text not in source:
            if len(span) == 1 and text not in missing:
                missing.append(text)
            continue
        cells = (wide or {}).get(text) if len(span) > 1 else None
        glyph = np.hstack([atlas.glyph_colours(code) for code in cells or source[text]])
        cuts = _cuts(ink_width(glyph), len(span), width, text)
        for code, (start, end) in zip(span, itertools.pairwise(cuts), strict=True):
            row, column = divmod(code, COLUMNS)
            cell = np.zeros((height, width), dtype=np.uint8)
            cell[:, : end - start] = glyph[:, start:end]
            pixels[row * height : (row + 1) * height, column * width : (column + 1) * width] = cell
        joins.update(
            {code: end - start - 1 for code, (start, end) in zip(span[:-1], itertools.pairwise(cuts[:-1]), strict=True)}
        )
    return Remapped(pixels, missing, atlas.palette, joins)


def _span(key: int | Span) -> Span:
    return key if isinstance(key, tuple) else (key,)


def _cuts(ink: int, codes: int, width: int, text: str) -> list[int]:
    """Where a glyph `ink` columns wide is cut for `codes` cells: whole cells first, the rest in the last.
    Every cell but the last keeps at least 2 columns, as a width of 0 would read as unset."""
    if not 2 * (codes - 1) < ink <= codes * width and not (codes == 1 and ink == 0):
        raise ValueError(f"{text!r} is {ink} pixels wide: it cannot be cut across {codes} cells of {width}")
    cuts = [0]
    for left in range(codes - 1, 0, -1):
        cuts.append(cuts[-1] + min(width, ink - cuts[-1] - 2 * left + 1))
    return [*cuts, ink]
