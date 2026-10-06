"""SNES planar tiles: 8x8 pixels of colour indices, 2 or 4 bits each.

A 2bpp tile is 8 rows of (plane 0, plane 1) byte pairs. A 4bpp tile is that
for planes 0/1, followed by the same for planes 2/3. Bit 7 is the leftmost pixel.
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from katsuji.atlas import Pixels


class TileOrder(Enum):
    """How the tiles of a pixel block are listed."""

    ROWS = "rows"
    """Left to right, then the next row of tiles."""
    COLUMNS = "columns"
    """Top to bottom, then the next column (a 16-pixel-tall glyph's two tiles stay together)."""


def colourize(ink: Pixels, ink_colour: int, paper_colour: int) -> Pixels:
    """Colour indices for 1bpp `ink`: `ink_colour` where set, `paper_colour` elsewhere.

    ff4 menus write ink 3 on paper 1 (plane 0 all set, plane 1 the glyph); dq6's
    4bpp items ink 15 on paper 14; cacheguard and dq6's battle text ink 3 on paper 0.
    """
    return np.where(ink != 0, ink_colour, paper_colour).astype(np.uint8)


def encode_tile(indices: Pixels, bpp: int) -> bytes:
    """One 8x8 tile of colour indices."""
    if indices.shape != (8, 8):
        raise ValueError(f"a tile is 8x8, got {indices.shape}")
    if bpp not in (2, 4):
        raise ValueError(f"bpp must be 2 or 4, got {bpp}")
    if int(indices.max(initial=0)) >= 1 << bpp:
        raise ValueError(f"colour {int(indices.max())} does not fit {bpp}bpp")
    planes = [np.packbits((indices >> plane) & 1, axis=1).ravel() for plane in range(bpp)]
    out = bytearray()
    for pair in range(0, bpp, 2):
        for row in range(8):
            out += bytes([planes[pair][row], planes[pair + 1][row]])
    return bytes(out)


def decode_tile(data: bytes, bpp: int) -> Pixels:
    """The 8x8 colour indices of one encoded tile."""
    raw = np.frombuffer(data, dtype=np.uint8)
    indices = np.zeros((8, 8), dtype=np.uint8)
    for pair in range(0, bpp, 2):
        block = raw[pair * 8 : pair * 8 + 16].reshape(8, 2)
        for offset in range(2):
            indices |= (np.unpackbits(block[:, offset]).reshape(8, 8) << (pair + offset)).astype(np.uint8)
    return indices


def encode_tiles(indices: Pixels, bpp: int, order: TileOrder = TileOrder.ROWS) -> bytes:
    """A block of colour indices (both sides multiples of 8) as consecutive tiles."""
    height, width = indices.shape
    if height % 8 or width % 8:
        raise ValueError(f"block is {height}x{width}, both sides must be multiples of 8")
    cells = [(row, column) for row in range(0, height, 8) for column in range(0, width, 8)]
    if order is TileOrder.COLUMNS:
        cells.sort(key=lambda cell: (cell[1], cell[0]))
    return b"".join(encode_tile(indices[row : row + 8, column : column + 8], bpp) for row, column in cells)


def pad_to_tiles(pixels: Pixels, fill: int = 0) -> Pixels:
    """`pixels` grown right and down to whole tiles."""
    height = -(-pixels.shape[0] // 8) * 8
    width = -(-pixels.shape[1] // 8) * 8
    padded = np.full((height, width), fill, dtype=np.uint8)
    padded[: pixels.shape[0], : pixels.shape[1]] = pixels
    return padded
