"""Word wrapping by pixel width, ff4's rules, with the game's control codes as data.

Measuring follows the runtime: each glyph advances `width + gap - kerning`,
the kerning taken against the previous glyph, so a word's measure carries
its trailing gap. Words are split on the space code; a word moves to a new
line when `line + word >= max_width`. Two ff4 details are kept on purpose:
after a break the line restarts at the word's width (no space counted), and
a word is kerned against the last glyph of the word before it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from katsuji.formats import VwfFont


@dataclass(frozen=True)
class Fixed:
    """A control code taking `arguments` bytes that prints `width` pixels (a name, a number)."""

    arguments: int
    width: int


@dataclass(frozen=True)
class Controls:
    """The game's text codes that are not glyphs.

    ff4: space `0xFF`, newline `0x01`, `0xFE n` switches to font `n`,
    `0x04 n` prints character `n`'s name (48 pixels), `0x08` the gil count (32).
    """

    space: int = 0xFF
    newline: int = 0x01
    font_switch: int | None = None
    fixed: Mapping[int, Fixed] = field(default_factory=dict)


@dataclass
class _Cursor:
    font: int
    previous: int | None


class Wrapper:
    """Measures and wraps encoded text set in `fonts` (font 0 unless switched)."""

    def __init__(self, fonts: Sequence[VwfFont], controls: Controls, gap: int = 1) -> None:
        self.fonts = list(fonts)
        self.controls = controls
        self.gap = gap

    def measure(self, codes: bytes, font: int = 0, previous: int | None = None) -> int:
        """Pixel width of `codes`, trailing gap included."""
        return self._walk(codes, _Cursor(font, previous))

    def wrap(self, codes: bytes, max_width: int, font: int = 0) -> tuple[bytes, int]:
        """`codes` with the spaces where a line would reach `max_width` turned
        into newlines, and the font active at the end."""
        out = bytearray()
        cursor = _Cursor(font, None)
        line = 0
        index = 0
        while index < len(codes):
            space = codes.find(self.controls.space, index)
            if space == -1:
                word = codes[index:]
                if index > 0:
                    fits = line + self._walk(word, _Cursor(cursor.font, cursor.previous)) < max_width
                    out.append(self.controls.space if fits else self.controls.newline)
                out += word
                self._walk(word, cursor)
                break
            word = codes[index:space]
            width = self._walk(word, _Cursor(cursor.font, cursor.previous))
            if line + width >= max_width:
                line = width
                out.append(self.controls.newline)
                cursor.previous = None
            else:
                if line > 0:
                    out.append(self.controls.space)
                line += width + self._space_width(cursor.font)
            out += word
            self._walk(word, cursor)
            index = space + 1
        return bytes(out), cursor.font

    def line_count(self, codes: bytes, max_width: int, font: int = 0) -> int:
        """Lines `codes` take once wrapped at `max_width`."""
        wrapped, _ = self.wrap(codes, max_width, font)
        return wrapped.count(self.controls.newline) - codes.count(self.controls.newline) + 1

    def _space_width(self, font: int) -> int:
        return self.fonts[font].widths[self.controls.space] + self.gap

    def _walk(self, codes: bytes, cursor: _Cursor) -> int:
        """Pixels `codes` advance from `cursor`; the cursor ends after them."""
        size = 0
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == self.controls.font_switch:
                index += 1
                cursor.font = codes[index]
                cursor.previous = None
            elif code in self.controls.fixed:
                fixed = self.controls.fixed[code]
                index += fixed.arguments
                size += fixed.width
                cursor.previous = None
            else:
                font = self.fonts[cursor.font]
                kerning = font.kerning.get((cursor.previous, code), 0) if cursor.previous is not None else 0
                size += font.widths[code] + self.gap - kerning
                cursor.previous = code
            index += 1
        return size
