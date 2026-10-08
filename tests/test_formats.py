import numpy as np
import pytest

from katsuji import Atlas, VwfFont
from katsuji.formats import pack_rows, unpack_rows
from katsuji.widths import apply_overrides


def _font(height: int = 1) -> VwfFont:
    return VwfFont(height, [bytes(height)] * 256, [0] * 256)


def test_rows_pack_leftmost_pixel_first() -> None:
    assert pack_rows(np.array([[1, 0, 1, 0, 1, 0, 1, 0]], dtype=np.uint8)) == bytes([0b10101010])


def test_narrow_glyphs_pad_on_the_right() -> None:
    assert pack_rows(np.array([[1, 1]], dtype=np.uint8)) == bytes([0b11000000])


def test_rows_wider_than_a_byte_are_rejected() -> None:
    wide = np.zeros((1, 9), dtype=np.uint8)
    with pytest.raises(ValueError, match="8 pixels per row"):
        pack_rows(wide)


def test_unpack_reverses_pack() -> None:
    assert unpack_rows(bytes([0b10000001])).tolist() == [[1, 0, 0, 0, 0, 0, 0, 1]]


def test_overrides_add_negatives_and_replace_positives() -> None:
    assert apply_overrides([5, 5, 5], {0: -1, 1: 3, 2: 0}) == [4, 3, 5]


def test_encode_sorts_kerning_by_the_16_bit_key() -> None:
    font = _font()
    font.kerning = {(2, 1): 1, (1, 2): 2}
    tail = font.encode()[256 * 2 :]
    assert tail == bytes([2, 0, 2, 1, 1, 1, 2, 2, 1])


def test_a_width_that_does_not_fit_a_byte_is_rejected() -> None:
    font = _font()
    font.widths[3] = 256
    with pytest.raises(ValueError, match="width 256"):
        font.encode()


def test_a_kerning_that_does_not_fit_a_byte_is_rejected() -> None:
    font = _font()
    font.kerning = {(1, 2): -1}
    with pytest.raises(ValueError, match="kerning of pair 0x01,0x02 -1"):
        font.encode()


def test_glyphs_must_match_the_font_height() -> None:
    font = _font(height=2)
    font.glyphs[0] = b"\x00"
    with pytest.raises(ValueError, match="1 rows, font height is 2"):
        font.encode()


def test_decode_reads_the_kerning_table() -> None:
    font = _font()
    font.kerning = {(1, 2): 3}
    assert VwfFont.decode(font.encode()).kerning == {(1, 2): 3}


def test_decode_rejects_trailing_bytes() -> None:
    data = _font().encode() + b"\x00"
    with pytest.raises(ValueError, match="describe"):
        VwfFont.decode(data)


def test_from_atlas_measures_then_overrides() -> None:
    pixels = np.zeros((1, 8 * 256), dtype=np.uint8)
    pixels[0, 2] = 1  # glyph 0: ink width 3
    font = VwfFont.from_atlas(Atlas(pixels, cell_width=8, cell_height=1), {1: 4})
    assert font.widths[:2] == [3, 4]
