import pytest

from katsuji import VwfFont
from katsuji.strings import index_entry, pack_runs, text_tiles
from katsuji.tiles import decode_tile

A = 1


def _font(height: int = 8, width: int = 5) -> VwfFont:
    glyphs = [bytes(height)] * 256
    glyphs[A] = bytes([0x80] * height)  # a vertical bar in column 0
    widths = [0] * 256
    widths[A] = width
    return VwfFont(height, glyphs, widths)


def test_tile_columns_round_the_width_up() -> None:
    _, columns = text_tiles(_font(), [A, A], bpp=2, ink_colour=3, paper_colour=1)
    assert columns == 2  # 5 + 1 + 5 = 11 pixels


def test_paper_fills_the_padding() -> None:
    tiles, _ = text_tiles(_font(), [A], bpp=2, ink_colour=3, paper_colour=1)
    assert decode_tile(tiles, 2)[0].tolist() == [3, 1, 1, 1, 1, 1, 1, 1]


def test_tall_fonts_list_a_column_s_two_tiles_together() -> None:
    tiles, columns = text_tiles(_font(height=16), [A], bpp=2, ink_colour=3, paper_colour=0)
    assert (columns, len(tiles)) == (1, 32)


def test_max_tiles_caps_the_columns() -> None:
    tiles, columns = text_tiles(_font(), [A] * 6, bpp=4, ink_colour=15, paper_colour=14, max_tiles=2)
    assert (columns, len(tiles)) == (2, 64)


def test_runs_never_straddle_a_bank() -> None:
    _, offsets = pack_runs([b"a" * 6, b"b" * 6], bank_size=8)
    assert offsets == [0, 8]


def test_runs_that_fit_stay_contiguous() -> None:
    blob, offsets = pack_runs([b"a" * 4, b"b" * 4], bank_size=8)
    assert (blob, offsets) == (b"aaaabbbb", [0, 4])


def test_a_run_larger_than_a_bank_is_rejected() -> None:
    runs = [b"a" * 9]
    with pytest.raises(ValueError, match="cannot fit one 8-byte bank"):
        pack_runs(runs, bank_size=8)


def test_index_entry_is_offset_bank_count() -> None:
    assert index_entry(0x2_1234, 7) == bytes([0x34, 0x12, 0x02, 0x07])


def test_index_entry_tile_count_fits_a_byte() -> None:
    with pytest.raises(ValueError, match="256 tiles"):
        index_entry(0, 256)
