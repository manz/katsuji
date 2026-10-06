from __future__ import annotations

import numpy as np

from katsuji import VwfFont, measure, render
from katsuji.render import advances, to_ascii

A, B = 1, 2


def _font() -> VwfFont:
    """1-pixel-tall glyphs: A = `##` (width 2), B = `#` (width 1)."""
    glyphs = [b"\x00"] * 256
    glyphs[A] = bytes([0b11000000])
    glyphs[B] = bytes([0b10000000])
    widths = [0] * 256
    widths[A], widths[B] = 2, 1
    return VwfFont(1, glyphs, widths)


def test_glyphs_are_separated_by_the_gap() -> None:
    assert to_ascii(render(_font(), [A, B])) == "##.#"


def test_kerning_removes_pixels_from_the_gap() -> None:
    font = _font()
    font.kerning = {(A, B): 1}
    assert to_ascii(render(font, [A, B])) == "###"


def test_measure_is_the_advance_without_a_trailing_gap() -> None:
    assert measure(_font(), [A, B, A]) == 2 + 1 + 1 + 1 + 2


def test_advances_list_each_pen_then_the_total() -> None:
    assert advances(_font(), [A, B]) == [0, 3, 4]


def test_ink_past_a_narrowed_width_still_draws_like_the_runtime() -> None:
    font = _font()
    font.widths[A] = 1  # narrower than its 2 ink columns
    assert to_ascii(render(font, [A, B])) == "###"


def test_empty_text_renders_nothing() -> None:
    assert render(_font(), []).shape == (1, 0)


def test_render_is_font_height_tall() -> None:
    font = VwfFont(2, [bytes([0x80, 0x80])] * 256, [1] * 256)
    assert render(font, [A]).tolist() == np.array([[1], [1]]).tolist()
