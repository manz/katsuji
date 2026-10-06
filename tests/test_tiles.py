from __future__ import annotations

import numpy as np
import pytest

from katsuji.tiles import TileOrder, colourize, decode_tile, encode_tile, encode_tiles, pad_to_tiles


def test_ff4_menu_convention_is_plane0_full_plane1_ink() -> None:
    ink = np.zeros((8, 8), dtype=np.uint8)
    ink[0, 0] = 1
    tile = encode_tile(colourize(ink, ink_colour=3, paper_colour=1), 2)
    assert tile[:4] == bytes([0xFF, 0x80, 0xFF, 0x00])


def test_dq6_4bpp_convention_puts_ink_in_plane0() -> None:
    ink = np.ones((8, 8), dtype=np.uint8)
    tile = encode_tile(colourize(ink, ink_colour=15, paper_colour=14), 4)
    assert tile == bytes([0xFF] * 32)


@pytest.mark.parametrize("bpp", [2, 4])
def test_decode_reverses_encode(bpp: int) -> None:
    indices = (np.arange(64, dtype=np.uint8).reshape(8, 8) % (1 << bpp)).astype(np.uint8)
    assert decode_tile(encode_tile(indices, bpp), bpp).tolist() == indices.tolist()


def test_a_colour_too_large_for_the_depth_is_rejected() -> None:
    indices = np.full((8, 8), 4, dtype=np.uint8)
    with pytest.raises(ValueError, match="does not fit 2bpp"):
        encode_tile(indices, 2)


def test_only_2_and_4_bpp() -> None:
    indices = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError, match="bpp must be 2 or 4"):
        encode_tile(indices, 3)


def test_a_tile_is_8x8() -> None:
    indices = np.zeros((8, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="8x8"):
        encode_tile(indices, 2)


def _two_by_two() -> np.ndarray:
    """A 16x16 block whose four tiles are colours 0, 1 (top right), 2 (bottom left), 3."""
    block = np.zeros((16, 16), dtype=np.uint8)
    block[:8, 8:] = 1
    block[8:, :8] = 2
    block[8:, 8:] = 3
    return block


def test_row_order_lists_tiles_left_to_right() -> None:
    data = encode_tiles(_two_by_two(), 2, TileOrder.ROWS)
    assert [decode_tile(data[i * 16 : i * 16 + 16], 2)[0, 0] for i in range(4)] == [0, 1, 2, 3]


def test_column_order_keeps_a_tall_glyph_together() -> None:
    data = encode_tiles(_two_by_two(), 2, TileOrder.COLUMNS)
    assert [decode_tile(data[i * 16 : i * 16 + 16], 2)[0, 0] for i in range(4)] == [0, 2, 1, 3]


def test_blocks_must_be_whole_tiles() -> None:
    block = np.zeros((8, 12), dtype=np.uint8)
    with pytest.raises(ValueError, match="multiples of 8"):
        encode_tiles(block, 2)


def test_pad_grows_to_whole_tiles() -> None:
    assert pad_to_tiles(np.ones((3, 9), dtype=np.uint8), fill=2).shape == (8, 16)
