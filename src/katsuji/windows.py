"""Paragraphs laid out by `TextLayout` and poured into fixed-size windows.

Which text opens a new window, how a speaker is marked, what counts as a
sentence: that is each game's script convention, kept in the game. It hands
`windows` its paragraphs already cut; katsuji does the rest:

- A paragraph's sentences share a line while they fit, the next one going on
  new lines of the same window while those fit, and in the next window when
  they do not. A sentence broken over lines shares its last line with none.
  One too wide for a narrower line it lands on is set again to that width
  before the window turns.
  A sentence longer than a whole window breaks over windows.
- A paragraph's `lead` (a speaker: "[D4]Cecil: ") opens it, and opens again
  every later window it carries onto.
- `Window` (katsuji.dialog's) gives the lines a window holds and their widths:
  `line_widths` narrows some (a page-turn arrow on the last one).
- Lines are measured through `TextLayout`, `measure_after` seeing every line
  laid out ahead in the same call, across windows: a font switch holds until
  the next one.

ff4's dialog (utils/dialog_layout.py) is the reference.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from katsuji.dialog import Window
from katsuji.layout import TextLayout


@dataclass(frozen=True)
class Paragraph:
    """Sentences that run on together. `lead` is set before the first, and again before the sentence that opens
    each later window; with `new_window`, the paragraph opens a window of its own."""

    sentences: Sequence[str]
    lead: str = ""
    new_window: bool = False


def windows(layout: TextLayout, paragraphs: Iterable[Paragraph], window: Window) -> list[list[str]]:
    """`paragraphs` laid out into windows of `window`'s size, each window as its lines."""
    filler = _Filler(layout, window)
    for paragraph in paragraphs:
        filler.paragraph(paragraph)
    return filler.close()


class _Filler:
    """The windows written so far and the one being filled."""

    def __init__(self, layout: TextLayout, window: Window) -> None:
        self.layout = layout
        self.window = window
        self.done: list[list[str]] = []
        self.lines: list[str] = []
        self.joinable = False  # the paragraph goes on: its next sentence takes no lead
        self.broken = False  # the open window's last line ends a sentence broken over lines: nothing joins it
        self.narrow: dict[int, TextLayout] = {}  # the layout set to each narrower line width, made once

    def paragraph(self, paragraph: Paragraph) -> None:
        if paragraph.new_window:
            self.turn()
        self.joinable = False
        for sentence in paragraph.sentences:
            self.add(sentence, paragraph.lead)

    def add(self, sentence: str, lead: str) -> None:
        """`sentence` on the last line when the paragraph goes on and it fits there, else on new lines of the open
        window, else in a new window, `lead` repeated. A sentence broken over lines leaves its last line to itself,
        as `TextLayout` lays a paragraph out."""
        if self.lines and self.joinable and not self.broken and not self.ended() and self.join(sentence):
            return
        text = sentence if self.joinable else lead + sentence
        if self.lines:
            lines = self.setting(text, self.lines)
            if self.fits([*self.lines, *lines]):
                self.lines.extend(lines)
                self.went_on(lines)
                return
            self.turn()
            text = lead + sentence
        lines = self.setting(text, [])
        self.fill(lines)
        self.went_on(lines)

    def went_on(self, lines: Sequence[str]) -> None:
        """A sentence was set as `lines`: the paragraph goes on, its last line closed when it broke."""
        self.joinable = True
        self.broken = len(lines) > 1

    def join(self, sentence: str) -> bool:
        """Put `sentence` after the last line, when the two still make one line that fits."""
        joined = self.set(f"{self.lines[-1]} {sentence}", self.ahead(self.lines[:-1]))
        if len(joined) == 1 and self.fits([*self.lines[:-1], joined[0]]):
            self.lines[-1] = joined[0]
            return True
        return False

    def setting(self, text: str, above: Sequence[str]) -> list[str]:
        """`text` set below the open window's `above` lines; set again to the narrowest line it lands on when a
        narrower line (a page-turn arrow) would not take it otherwise."""
        before = self.ahead(above)
        lines = self.set(text, before)
        rows = range(len(above), min(len(above) + len(lines), self.window.lines))
        if self.fits([*above, *lines]) or not rows:
            return lines
        width = min(self.window.line_width(row) for row in rows)
        if width >= self.layout.width:
            return lines
        if width not in self.narrow:
            self.narrow[width] = replace(
                self.layout, width=width, min_balanced_width=min(self.layout.min_balanced_width, width)
            )
        narrowed = [line for block in self.narrow[width].blocks(text, before) for line in block]
        return narrowed if self.fits([*above, *narrowed]) else lines

    def set(self, text: str, before: str) -> list[str]:
        """`text` typeset and wrapped to the layout's width, `before` laid out ahead of it."""
        return [line for block in self.layout.blocks(text, before) for line in block]

    def ended(self) -> bool:
        """The open window's last line ends with an editor's line break: it takes nothing more."""
        return bool(self.layout.line_breaks) and self.lines[-1].endswith(self.layout.line_breaks)

    def fits(self, lines: Sequence[str]) -> bool:
        """`lines` fit the open window from its top: no more than it holds, each no wider than its line."""
        if len(lines) > self.window.lines:
            return False
        before = self.ahead()
        for row, line in enumerate(lines):
            if self.layout.measure_line(line, before) > self.window.line_width(row):
                return False
            before = f"{before}\n{line}" if before else line
        return True

    def fill(self, lines: list[str]) -> None:
        """`lines` over windows, each turned at the last line that fits."""
        while lines:
            taken = len(lines)
            while taken > 1 and not self.fits(lines[:taken]):
                taken -= 1
            self.lines = lines[:taken]
            lines = lines[taken:]
            if lines:
                self.turn()

    def turn(self) -> None:
        """Close the open window: the next text opens a new one."""
        if self.lines:
            self.done.append(self.lines)
            self.lines = []
        self.joinable = False

    def ahead(self, lines: Sequence[str] = ()) -> str:
        """The text laid out in the windows closed so far, then `lines`."""
        return "\n".join(line for window in [*self.done, lines] for line in window)

    def close(self) -> list[list[str]]:
        self.turn()
        return self.done
