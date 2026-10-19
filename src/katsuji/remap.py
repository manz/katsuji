"""A font moved from one game's text table to another's: the same glyphs, at the codes the other table gives them."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from katsuji.atlas import Atlas, Pixels

COLUMNS = 16
GLYPHS = 256


def table_codes(path: Path) -> dict[str, int]:
    """The one-byte codes of a `.tbl` (`XX=text`), by text; the first code a text has wins."""
    codes: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, text = line.partition("=")
        if not sep or len(key) != 2 or not text:
            continue
        try:
            code = int(key, 16)
        except ValueError:
            continue
        codes.setdefault(text, code)
    return codes


@dataclass(frozen=True)
class Remapped:
    pixels: Pixels
    """The new atlas: 16 cells per row, 256 cells, each glyph at its target code. Colour indices when the source
    PNG is palettized, else ink (1) and paper (0)."""
    missing: list[str]
    """Texts the target table has that the source font doesn't draw."""
    palette: tuple[int, ...] | None = None
    """The source PNG's palette, to write the new one with."""


def remap(atlas: Atlas, source: dict[str, int], target: dict[str, int]) -> Remapped:
    """Each text of `target` gets the source glyph that `source` gives the same text; the other cells stay blank."""
    width, height = atlas.cell_width, atlas.cell_height
    pixels = np.zeros((GLYPHS // COLUMNS * height, COLUMNS * width), dtype=np.uint8)
    missing = []
    for text, code in sorted(target.items(), key=lambda item: item[1]):
        if text not in source:
            missing.append(text)
            continue
        row, column = divmod(code, COLUMNS)
        cell = atlas.glyph_colours(source[text])
        pixels[row * height : (row + 1) * height, column * width : (column + 1) * width] = cell
    return Remapped(pixels, missing, atlas.palette)
