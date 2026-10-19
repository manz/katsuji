"""Fonts a game reads straight from ROM, as its own glyph layout rather than katsuji's VWF file.

- `tiles`: one SNES planar tile (or block of tiles) per glyph, the cell's colour indices at 2 or 4 bpp: FF6's
  8x8 menu font.
- `rows16`: 1bpp rows 16 pixels wide, each a little-endian 16-bit word whose bit 15 is the leftmost pixel, the
  glyph drawn `x_offset` pixels into the row; the advance widths are a separate table, one byte per code: FF6's
  dialogue font.

Both list glyphs `first` to `first + count - 1` and may be padded to a fixed size.
"""

from collections.abc import Mapping

import numpy as np

from katsuji.atlas import Atlas, Pixels
from katsuji.tiles import encode_tiles
from katsuji.widths import apply_overrides

CODES = 256


def _padded(data: bytes, size: int | None) -> bytes:
    if size is None:
        return data
    if len(data) > size:
        raise ValueError(f"{len(data)} bytes of glyphs do not fit the {size}-byte size")
    return data + bytes(size - len(data))


def encode_tile_font(atlas: Atlas, bpp: int, first: int = 0, count: int = CODES, size: int | None = None) -> bytes:
    """Glyphs `first`.. as tiles of their colour indices, each cell's tiles left to right, then down."""
    data = b"".join(encode_tiles(atlas.glyph_colours(code), bpp) for code in range(first, first + count))
    return _padded(data, size)


def pack_rows16(glyph: Pixels, x_offset: int) -> bytes:
    """One glyph as 16-pixel rows, `x_offset` pixels in."""
    if x_offset + glyph.shape[1] > 16:
        raise ValueError(f"a {glyph.shape[1]}-pixel glyph at x {x_offset} does not fit a 16-pixel row")
    out = bytearray()
    for row in glyph:
        word = 0
        for column in np.flatnonzero(row):
            word |= 0x8000 >> (int(column) + x_offset)
        out += word.to_bytes(2, "little")
    return bytes(out)


def unpack_rows16(data: bytes, height: int, x_offset: int, width: int) -> Pixels:
    """The `width`-pixel glyph a `pack_rows16` record of `height` rows describes."""
    glyph = np.zeros((height, width), dtype=np.uint8)
    for row in range(height):
        word = int.from_bytes(data[2 * row : 2 * row + 2], "little")
        for column in range(width):
            glyph[row, column] = word >> (15 - x_offset - column) & 1
    return glyph


def encode_rows16_font(
    atlas: Atlas, x_offset: int, first: int = 0, count: int = CODES, size: int | None = None
) -> bytes:
    """Glyphs `first`.. as `pack_rows16` records."""
    data = b"".join(pack_rows16(atlas.glyph(code), x_offset) for code in range(first, first + count))
    return _padded(data, size)


def rows16_widths(
    atlas: Atlas, spacing: int, overrides: Mapping[int, int], first: int = 0, count: int = CODES
) -> bytes:
    """One advance width per code: the ink plus `spacing` for the drawn glyphs (0 for blank cells and codes outside
    the font), then `overrides` (see `apply_overrides`)."""
    measured = [0] * CODES
    for code in range(first, first + count):
        ink = atlas.ink_width(code)
        measured[code] = ink + spacing if ink else 0
    widths = apply_overrides(measured, overrides)
    if any(not 0 <= width <= 0xFF for width in widths):
        raise ValueError("a width does not fit a byte")
    return bytes(widths)
