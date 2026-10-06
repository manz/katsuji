"""`WindowBuilder` on its own: a 2-line window, every glyph advancing 4 pixels."""

from __future__ import annotations

from katsuji import VwfFont
from katsuji.dialog import Window, WindowBuilder
from katsuji.wrap import Controls, Wrapper


class _Letters:
    """A table where each letter is its own code and a space is 0xFF."""

    def to_bytes(self, text: str) -> bytes:
        return bytes(0xFF if char == " " else 0x01 if char == "\n" else ord(char) for char in text)

    def to_text(self, data: bytes) -> str:
        return "".join(" " if code == 0xFF else "\n" if code == 0x01 else chr(code) for code in data)


def _builder(width: int = 40, line_widths: dict[int, int] | None = None) -> WindowBuilder:
    font = VwfFont(1, [b"\x00"] * 256, [3] * 256)
    wrapper = Wrapper([font], Controls(space=0xFF, newline=0x01))
    return WindowBuilder(_Letters(), wrapper, Window(width, 2, line_widths=line_widths, new_window="|"))


def test_text_that_fits_shares_a_window() -> None:
    windows = _builder()
    windows.add("ab")
    windows.add("cd")
    assert windows.result() == ["ab\ncd"]


def test_overflow_opens_a_new_window_with_the_marker() -> None:
    windows = _builder()
    for text in ("ab", "cd", "ef"):
        windows.add(text)
    assert windows.result() == ["ab\ncd|", "ef"]


def test_a_narrower_line_can_overflow_the_window() -> None:
    windows = _builder(line_widths={1: 4})
    windows.add("ab")
    windows.add("cd")
    assert windows.result() == ["ab|", "cd"]


def test_emit_writes_a_block_of_its_own() -> None:
    windows = _builder()
    windows.add("ab")
    windows.emit("cd", marker=True)
    assert windows.result() == ["ab", "cd|"]


def test_append_before_any_window_starts_one() -> None:
    windows = _builder()
    windows.append("[end]")
    assert windows.result() == ["[end]"]


def test_append_glues_to_the_last_window_written() -> None:
    windows = _builder()
    windows.emit("ab")
    windows.append("[delay]")
    assert windows.result() == ["ab[delay]"]
