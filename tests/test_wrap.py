"""Wrapping, checked against ff4's own `TextMetrics.word_warp`.

`fixtures/ff4/wrap_goldens.json` holds ff4's results on its dialog lines at
208 pixels (the dialog window) and 120 (more breaks), recorded with ff4's
metrics.py on its built fonts. Lines with the gil code (0x08) are left out:
ff4 measures them with a bug (`size = 32` instead of `+=`) that katsuji fixes.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from script import Table

from katsuji import VwfFont
from katsuji.wrap import Controls, Fixed, Wrapper

FF4 = Path(__file__).parent / "fixtures" / "ff4"
FF4_CONTROLS = Controls(space=0xFF, newline=0x01, font_switch=0xFE, fixed={0x04: Fixed(1, 48), 0x08: Fixed(0, 32)})
GOLDENS: list[dict[str, Any]] = json.loads((FF4 / "wrap_goldens.json").read_text())


@pytest.fixture(scope="module")
def ff4_wrapper() -> Wrapper:
    fonts = [
        VwfFont.decode((FF4 / name).read_bytes())
        for name in ("font.dat", "wicked_font.dat", "book_font.dat", "bold_font.dat")
    ]
    return Wrapper(fonts, FF4_CONTROLS)


@pytest.mark.parametrize("case", GOLDENS, ids=[f"{i}@{c['width']}" for i, c in enumerate(GOLDENS)])
def test_wraps_like_ff4(ff4_wrapper: Wrapper, dialog_table: Table, case: dict[str, Any]) -> None:
    wrapped, font = ff4_wrapper.wrap(dialog_table.to_bytes(case["text"]), case["width"])
    assert (dialog_table.to_text(wrapped), font) == (case["wrapped"], case["font"])


A, B, SPACE, NEWLINE = 0x10, 0x11, 0xFF, 0x01


def _wrapper(**controls: Any) -> Wrapper:
    """Every glyph 3 pixels wide, the space 2, gap 1: a letter advances 4, a space 3."""
    widths = [3] * 256
    widths[SPACE] = 2
    font = VwfFont(1, [b"\x00"] * 256, widths)
    return Wrapper([font], Controls(space=SPACE, newline=NEWLINE, **controls))


def test_measure_counts_the_trailing_gap() -> None:
    assert _wrapper().measure(bytes([A, B])) == 8


def test_kerning_tightens_the_measure() -> None:
    wrapper = _wrapper()
    wrapper.fonts[0].kerning = {(A, B): 2}
    assert wrapper.measure(bytes([A, B])) == 6


def test_a_word_reaching_the_width_starts_a_new_line() -> None:
    text = bytes([A, A, SPACE, B, B])  # 8 + space 3 + 8 = 19
    assert _wrapper().wrap(text, 19)[0] == bytes([A, A, NEWLINE, B, B])


def test_words_that_fit_keep_their_space() -> None:
    text = bytes([A, A, SPACE, B, B])
    assert _wrapper().wrap(text, 20)[0] == text


def test_a_single_long_word_is_not_broken() -> None:
    assert _wrapper().wrap(bytes([A] * 10), 8)[0] == bytes([A] * 10)


def test_fixed_codes_count_their_width_and_skip_arguments() -> None:
    wrapper = _wrapper(fixed={0x04: Fixed(1, 48)})
    assert wrapper.measure(bytes([0x04, A, B])) == 48 + 4


def test_the_gil_code_adds_instead_of_replacing() -> None:
    """ff4 set the size to 32 on 0x08, dropping what came before it."""
    wrapper = _wrapper(fixed={0x08: Fixed(0, 32)})
    assert wrapper.measure(bytes([A, 0x08])) == 4 + 32


def test_font_switch_changes_the_widths() -> None:
    narrow = VwfFont(1, [b"\x00"] * 256, [1] * 256)
    wrapper = _wrapper(font_switch=0xFE)
    wrapper.fonts.append(narrow)
    assert wrapper.measure(bytes([A, 0xFE, 1, A])) == 4 + 2


def test_wrap_reports_the_font_left_active() -> None:
    wrapper = _wrapper(font_switch=0xFE)
    wrapper.fonts.append(wrapper.fonts[0])
    assert wrapper.wrap(bytes([A, 0xFE, 1]), 100)[1] == 1


def test_line_count_counts_inserted_breaks() -> None:
    """At 16: AA (8 + space 3 = 11), BB would reach 19 so breaks (line restarts at 8), AA reaches 16 too."""
    text = bytes([A, A, SPACE, B, B, SPACE, A, A])
    assert _wrapper().line_count(text, 16) == 3
