"""A font moved from one game's text table to another's: the same glyphs, at the codes the other table gives them."""

import itertools
from collections import Counter
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
"""A game's table as `remap` takes it: by code (`table_texts`), or by span (`table_spans`)."""


def table_texts(path: Path | str) -> dict[int, str]:
    """The text of every one-byte code of a `.tbl` (`XX=text`); a text may have several codes."""
    return {span[0]: text for span, text in table_spans(path).items() if len(span) == 1}


def table_codes(path: Path | str) -> dict[str, int]:
    """The one-byte codes of a `.tbl` (`XX=text`), by text; the first code a text has wins."""
    codes: dict[str, int] = {}
    for span, text in _entries(Path(path)):
        if len(span) == 1:
            codes.setdefault(text, span[0])
    return codes


def table_spans(path: Path | str) -> dict[Span, str]:
    """`table_texts` with the runs of codes one character is drawn on (`A0A1=œ`). A run whose text is several
    characters is a control or a DTE pair, not a glyph, and is left out."""
    texts: dict[Span, str] = {}
    for span, text in _entries(Path(path)):
        texts.setdefault(span, text)
    return texts


def wide_spans(target: Target) -> dict[Span, str]:
    """The runs of `target` that are one glyph cut across cells: none of their codes is a code of its own or
    of another run. ff6's `74C0=«` beside `C0=°` writes two glyphs, not one wide one."""
    used = Counter(code for key in target for code in _span(key))
    shared = {code for code, count in used.items() if count > 1}
    return {
        span: text
        for span, text in ((_span(key), text) for key, text in target.items())
        if len(span) > 1 and not shared.intersection(span)
    }


CJK_BLOCKS = ((0x3000, 0x30FF), (0x3400, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF))
"""CJK punctuation and kana, ideographs, hangul, compatibility ideographs, full- and halfwidth forms."""


def is_cjk(text: str) -> bool:
    """A kanji, kana or CJK form: a game's two-byte codes for these index its own glyph set, not cells."""
    return any(low <= ord(text) <= high for low, high in CJK_BLOCKS)


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
    """Texts the target table has that the source font doesn't draw (a wide run's too, kanji aside)."""
    palette: tuple[int, ...] | None = None
    """The source PNG's palette, to write the new one with."""
    joins: dict[int, int] = field(default_factory=dict)
    """The advance width of each code a glyph continues past (a wide run's codes but the last): its cut, less
    the 1-pixel gap the engine adds, so the next cell's pixels follow on. 0 is a width here."""


def remap(
    atlas: Atlas, source: Mapping[str, int | Span], target: Target, wide: Mapping[str, Span] | None = None
) -> Remapped:
    """Each code of `target` gets the source glyph that `source` gives its text, every code a text has; the
    other cells stay blank. A wide run (`wide_spans`) gets its glyph cut across its codes, from `wide` when the
    source draws the text wider there."""
    width, height = atlas.cell_width, atlas.cell_height
    pixels = np.zeros((GLYPHS // COLUMNS * height, COLUMNS * width), dtype=np.uint8)
    missing: list[str] = []
    joins: dict[int, int] = {}
    runs = wide_spans(target)
    singles = sorted(
        (span, text) for span, text in ((_span(key), text) for key, text in target.items()) if len(span) == 1
    )
    for span, text in [*singles, *sorted(runs.items())]:
        if text not in source:
            if text not in missing and not (len(span) > 1 and is_cjk(text)):
                missing.append(text)
            continue
        cells = (wide or {}).get(text) if len(span) > 1 else None
        glyph = np.hstack([atlas.glyph_colours(code) for code in cells or _span(source[text])])
        cuts = _cuts(ink_width(glyph), len(span), width, text)
        for code, (start, end) in zip(span, itertools.pairwise(cuts), strict=True):
            row, column = divmod(code, COLUMNS)
            cell = np.zeros((height, width), dtype=np.uint8)
            cell[:, : end - start] = glyph[:, start:end]
            pixels[row * height : (row + 1) * height, column * width : (column + 1) * width] = cell
        for code, (start, end) in zip(span[:-1], itertools.pairwise(cuts), strict=False):
            joins[code] = end - start - 1
    return Remapped(pixels, missing, atlas.palette, joins)


def _span(key: int | Span) -> Span:
    return key if isinstance(key, tuple) else (key,)


def _cuts(ink: int, codes: int, width: int, text: str) -> list[int]:
    """Where a glyph `ink` columns wide is cut for `codes` cells: whole cells first, the rest in the last. A
    code advances its slice, so each one before the last keeps at least a column; past the ink they are blank."""
    if not codes - 1 <= ink <= codes * width:
        raise ValueError(f"{text!r} is {ink} pixels wide: it cannot be cut across {codes} cells of {width}")
    cuts = [0]
    for after in range(codes - 2, -1, -1):
        cuts.append(cuts[-1] + min(width, ink - cuts[-1] - after))
    return [*cuts, ink]
