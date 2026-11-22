"""Windows drawn as the game draws them, one framed panel under the other: a dialog's preview.

The game draws each line (its fonts, its table, its inserts, as `banner` does); `window_sheet` lays the lines out
in `Window`s. A sheet is colour indices into `PALETTE`, a palettized PNG away (`katsuji.png.encode`):

- a row narrower than the window (`line_widths`, a page-turn arrow) is shaded past its width;
- ink past a row's width is `OVER`, and so is every line past the lines a window holds: what overflows shows;
  in a window that scrolls (`Window.scrolls`), those lines are inked on shade: scrolled to, not overflowing.
"""

from collections.abc import Sequence

import numpy as np

from katsuji.dialog import Window
from katsuji.png import Pixels

BACK, PAPER, INK, FRAME, OVER, SHADE = range(6)
PALETTE = (
    *(0x10, 0x10, 0x18),  # BACK: around the windows
    *(0x20, 0x30, 0x88),  # PAPER
    *(0xF8, 0xF8, 0xF8),  # INK
    *(0xC8, 0xC8, 0xD0),  # FRAME
    *(0xFF, 0x40, 0x40),  # OVER
    *(0x18, 0x24, 0x60),  # SHADE: past a narrower row
)


def window_sheet(windows: Sequence[Sequence[Pixels]], window: Window, line_height: int, margin: int = 4) -> Pixels:
    """`windows`, each its lines drawn (0 paper, anything else ink), as framed panels `margin` pixels apart, each
    line `line_height` rows tall. Panels are as wide as the window, or as its widest line when one is wider."""
    width = max([window.width, *(line.shape[1] for lines in windows for line in lines)])
    panels = [_framed(_panel(lines, window, line_height, width), margin) for lines in windows]
    if not panels:
        return np.full((0, 0), BACK, dtype=np.uint8)
    gap = np.full((margin, panels[0].shape[1]), BACK, dtype=np.uint8)
    stacked = [part for panel in panels for part in (gap, panel)][1:]
    return np.pad(np.concatenate(stacked), margin, constant_values=BACK)


def _panel(lines: Sequence[Pixels], window: Window, line_height: int, width: int) -> Pixels:
    """A window's inside: its rows, each shaded past its width, its lines inked."""
    rows = max(window.lines, len(lines))
    panel = np.full((rows * line_height, width), PAPER, dtype=np.uint8)
    for row in range(rows):
        held = row < window.lines or window.scrolls
        limit = window.line_width(row) if held else 0
        panel[row * line_height : (row + 1) * line_height, 0 if row >= window.lines else limit :] = SHADE
        if row < len(lines):
            _ink(panel[row * line_height : (row + 1) * line_height], lines[row], limit)
    return panel


def _ink(band: Pixels, line: Pixels, limit: int) -> None:
    """`line` inked onto its row's `band`: `INK` within `limit` pixels, `OVER` past them."""
    piece = line[: band.shape[0]] != 0
    columns = np.arange(piece.shape[1])
    target = band[: piece.shape[0], : piece.shape[1]]
    target[piece & (columns < limit)] = INK
    target[piece & (columns >= limit)] = OVER


def _framed(panel: Pixels, margin: int) -> Pixels:
    return np.pad(np.pad(panel, margin, constant_values=PAPER), 1, constant_values=FRAME)
