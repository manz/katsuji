"""Text windows: wrap text and fill fixed-size windows with it.

Which text opens a new window, how a speaker is marked, what counts as a
sentence: that is each game's script convention, kept in the game. katsuji
gives the pieces those rules drive:

- `Window`: how many lines a window holds and how wide each line may be.
- `WindowBuilder`: wraps text and fills windows in order, opening a new one
  when text would overflow, writing the game's new-window marker between them.

`tests/ff4_dialog.py` is ff4's French script rules written on top of them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from katsuji.wrap import Wrapper


class TextTable(Protocol):
    """What a816's `script.Table` offers: text to codes and back."""

    def to_bytes(self, text: str) -> bytes: ...

    def to_text(self, data: bytes) -> str: ...


@dataclass(frozen=True)
class Window:
    """A text window: `lines` lines of `width` pixels, unless `line_widths` narrows some.

    ff4's dialog window is 4 lines of 208 pixels, the last one 200 (the
    prompt arrow sits there): `Window(208, 4, line_widths={3: 200})`.
    """

    width: int
    lines: int
    line_widths: dict[int, int] | None = None
    new_window: str = "[new]"
    """Written at the end of a window that another follows."""

    def line_width(self, line: int) -> int:
        return (self.line_widths or {}).get(line, self.width)


class WindowBuilder:
    """Fills windows with wrapped text, in order.

    Text is wrapped at the window width (lines are newline-separated in the
    result); a window is closed with `window.new_window` when the next text
    would not fit, or when the caller breaks it.
    """

    def __init__(self, table: TextTable, wrapper: Wrapper, window: Window) -> None:
        self.table = table
        self.wrapper = wrapper
        self.window = window
        self.font = 0
        self.windows: list[str] = []
        self.pending: list[str] = []

    def wrap(self, text: str) -> str:
        """`text` wrapped at the window width, carrying the active font across calls."""
        wrapped, self.font = self.wrapper.wrap(self.table.to_bytes(text), self.window.width, self.font)
        return self.table.to_text(wrapped)

    def fits(self, wrapped: str) -> bool:
        """`wrapped` (newline-separated lines) fits one window, each line its width."""
        lines = wrapped.split("\n")
        if len(lines) > self.window.lines:
            return False
        return all(
            self.wrapper.measure(self.table.to_bytes(line)) <= self.window.line_width(index)
            for index, line in enumerate(lines)
            if index in (self.window.line_widths or {})
        )

    @property
    def filling(self) -> bool:
        """A window has text that is not written out yet."""
        return bool(self.pending)

    def add(self, text: str) -> None:
        """Wrap `text` into the open window, or close it and start a new one when it would overflow."""
        wrapped = self.wrap(text)
        if self.pending and not self.fits("\n".join([*self.pending, wrapped])):
            self.break_window()
        self.pending.append(wrapped)

    def break_window(self, marker: bool = True) -> None:
        """Close the open window, with the new-window marker unless `marker` is False."""
        if self.pending:
            self.windows.append("\n".join(self.pending) + (self.window.new_window if marker else ""))
            self.pending = []

    def emit(self, text: str, marker: bool = False) -> None:
        """Close the open window, then write `text` (wrapped) as a block of its own."""
        self.break_window(marker=False)
        self.windows.append(self.wrap(text) + (self.window.new_window if marker else ""))

    def append(self, text: str) -> None:
        """Add `text` as is to the end of the open window, or of the last one written."""
        if self.pending:
            self.pending[-1] += text
        elif self.windows:
            self.windows[-1] += text
        else:
            self.windows.append(text)

    def result(self) -> Sequence[str]:
        """Every window, the open one closed without a marker."""
        self.break_window(marker=False)
        return self.windows
