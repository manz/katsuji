"""`window_sheet`: windows drawn as framed panels, overflow shown."""

import numpy as np

from katsuji.dialog import Window
from katsuji.png import Pixels
from katsuji.sheet import BACK, FRAME, INK, OVER, PAPER, SHADE, window_sheet


def line(width: int) -> Pixels:
    return np.ones((2, width), dtype=np.uint8)


def inside(sheet: Pixels, margin: int = 1) -> Pixels:
    """The first panel's inside, past the sheet's margin, the frame and the panel's own margin."""
    start = 2 * margin + 1
    return sheet[start:, start:]


def test_no_window_is_an_empty_sheet() -> None:
    assert window_sheet([], Window(4, 1), 2).shape == (0, 0)


def test_a_panel_is_framed_and_set_in_the_margin() -> None:
    sheet = window_sheet([[line(2)]], Window(4, 1), 2, margin=1)
    assert (sheet[0, 0], sheet[1, 1], sheet[2, 2]) == (BACK, FRAME, PAPER)


def test_a_sheet_is_as_big_as_its_windows() -> None:
    assert window_sheet([[line(2)], [line(2)]], Window(4, 1), 2, margin=1).shape == (2 * 6 + 1 + 2, 4 + 2 + 2 + 2)


def test_a_line_is_inked() -> None:
    assert inside(window_sheet([[line(2)]], Window(4, 1), 2, margin=1))[0, :3].tolist() == [INK, INK, PAPER]


def test_a_narrower_row_is_shaded_past_its_width() -> None:
    sheet = window_sheet([[]], Window(4, 1, line_widths={0: 2}), 2, margin=1)
    assert inside(sheet)[0, :4].tolist() == [PAPER, PAPER, SHADE, SHADE]


def test_ink_past_a_row_is_over() -> None:
    sheet = window_sheet([[line(6)]], Window(4, 1), 2, margin=1)
    assert inside(sheet)[0, :6].tolist() == [INK] * 4 + [OVER] * 2


def test_a_line_past_the_window_is_over() -> None:
    sheet = window_sheet([[line(1), line(1)]], Window(4, 1), 2, margin=1)
    assert inside(sheet)[2, :2].tolist() == [OVER, SHADE]


def test_a_line_taller_than_its_row_is_cut() -> None:
    tall = np.ones((5, 1), dtype=np.uint8)
    assert window_sheet([[tall]], Window(4, 1), 2, margin=1).shape == (2 + 2 * 1 + 2 * 1 + 2, 4 + 2 + 2 + 2)


def test_a_line_scrolled_to_is_inked_on_shade() -> None:
    sheet = window_sheet([[line(1), line(1)]], Window(4, 1, scrolls=True), 2, margin=1)
    assert inside(sheet)[2, :2].tolist() == [INK, SHADE]
