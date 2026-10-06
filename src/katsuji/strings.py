"""Static strings: text pre-rendered to tiles at build time, packed into one blob.

For text known at build time (item names, menu labels), the runtime then only
copies tiles. Rendering goes through `render`, so a static string has the
pixels the runtime renderer would have drawn.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from katsuji.formats import VwfFont
from katsuji.render import render
from katsuji.tiles import TileOrder, colourize, encode_tiles, pad_to_tiles

BANK = 0x10000


def text_tiles(
    font: VwfFont,
    codes: Sequence[int],
    bpp: int,
    ink_colour: int,
    paper_colour: int,
    gap: int = 1,
    max_tiles: int | None = None,
) -> tuple[bytes, int]:
    """`codes` rendered and encoded as tiles, with the number of tile columns.

    A 16-pixel-tall font yields two tiles per column, listed column by column.
    `max_tiles` caps the columns (the rest of the text is dropped).
    """
    pixels = pad_to_tiles(colourize(render(font, codes, gap), ink_colour, paper_colour), fill=paper_colour)
    columns = pixels.shape[1] // 8
    if max_tiles is not None and columns > max_tiles:
        pixels = pixels[:, : max_tiles * 8]
        columns = max_tiles
    return encode_tiles(pixels, bpp, TileOrder.COLUMNS), columns


def pack_runs(runs: Sequence[bytes], bank_size: int = BANK) -> tuple[bytes, list[int]]:
    """Concatenate `runs`, padding so none straddles a `bank_size` edge (a DMA
    source cannot wrap a bank). Place the blob on a bank boundary to keep the
    edges real. Returns the blob and each run's offset."""
    blob = bytearray()
    offsets = []
    for run in runs:
        if len(run) > bank_size:
            raise ValueError(f"a {len(run)}-byte run cannot fit one {bank_size}-byte bank")
        room = bank_size - len(blob) % bank_size
        if len(run) > room:
            blob += bytes(room)
        offsets.append(len(blob))
        blob += run
    return bytes(blob), offsets


def index_entry(offset: int, tiles: int) -> bytes:
    """4 bytes locating a run in a bank-aligned blob: offset low 16 bits, bank, tile count."""
    if not 0 <= tiles <= 0xFF:
        raise ValueError(f"{tiles} tiles do not fit a byte")
    return struct.pack("<HBB", offset & 0xFFFF, offset >> 16, tiles)
