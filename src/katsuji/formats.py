"""The VWF font file the a816 runtime reads.

Layout, all little-endian:

- 256 glyph records: `height` bytes of 1bpp rows (bit 7 is the leftmost
  pixel), then one advance-width byte. A glyph is found at `code * (height + 1)`.
- `u16` kerning pair count, then that many 3-byte entries `left, right, pixels`,
  sorted by `left | right << 8` (the SNES binary-searches that 16-bit key).
  `pixels` is how much the gap after `left` shrinks before `right`.
- one byte: `height`.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from katsuji.atlas import Atlas, Pixels
from katsuji.widths import apply_overrides, measured_widths

GLYPHS = 256


def pack_rows(glyph: Pixels) -> bytes:
    """One byte per row, bit 7 first; glyphs wider than 8 pixels are rejected."""
    if glyph.shape[1] > 8:
        raise ValueError(f"1bpp records hold 8 pixels per row, got a {glyph.shape[1]}-pixel glyph")
    padded = np.zeros((glyph.shape[0], 8), dtype=np.uint8)
    padded[:, : glyph.shape[1]] = glyph != 0
    return bytes(np.packbits(padded, axis=1).ravel())


def unpack_rows(data: bytes) -> Pixels:
    """The 8-pixel-wide glyph a `pack_rows` record describes."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8)).reshape(len(data), 8)


@dataclass
class VwfFont:
    """Glyph bitmaps, advance widths and kerning pairs of one font."""

    height: int
    glyphs: list[bytes]
    widths: list[int]
    kerning: dict[tuple[int, int], int] = field(default_factory=dict)

    @classmethod
    def from_atlas(
        cls,
        atlas: Atlas,
        width_overrides: Mapping[int, int] | None = None,
        kerning: Mapping[tuple[int, int], int] | None = None,
    ) -> VwfFont:
        """The first 256 cells of `atlas`, widths measured from the ink then overridden."""
        glyphs = [pack_rows(atlas.glyph(index)) for index in range(GLYPHS)]
        widths = apply_overrides(measured_widths(atlas, GLYPHS), width_overrides or {})
        return cls(atlas.cell_height, glyphs, widths, dict(kerning or {}))

    def glyph(self, code: int) -> Pixels:
        return unpack_rows(self.glyphs[code])

    def encode(self) -> bytes:
        out = bytearray()
        for rows, width in zip(self.glyphs, self.widths, strict=True):
            if len(rows) != self.height:
                raise ValueError(f"glyph has {len(rows)} rows, font height is {self.height}")
            out += rows
            out.append(_byte(width, "width"))
        pairs = sorted(self.kerning.items(), key=lambda item: item[0][0] | item[0][1] << 8)
        out += struct.pack("<H", len(pairs))
        for (left, right), pixels in pairs:
            out += bytes([left, right, _byte(pixels, f"kerning of pair {left:#04x},{right:#04x}")])
        out.append(self.height)
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> VwfFont:
        height = data[-1]
        record = height + 1
        glyphs = [data[code * record : code * record + height] for code in range(GLYPHS)]
        widths = [data[code * record + height] for code in range(GLYPHS)]
        offset = GLYPHS * record
        (count,) = struct.unpack_from("<H", data, offset)
        kerning: dict[tuple[int, int], int] = {}
        for entry in range(count):
            left, right, pixels = data[offset + 2 + entry * 3 : offset + 5 + entry * 3]
            kerning[(left, right)] = pixels
        if offset + 2 + count * 3 + 1 != len(data):
            raise ValueError(f"font is {len(data)} bytes, its tables describe {offset + 2 + count * 3 + 1}")
        return cls(height, glyphs, widths, kerning)


def _byte(value: int, what: str) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{what} {value} does not fit a byte")
    return value
