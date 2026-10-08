"""A font drawn as a PNG grid of fixed-size cells, one glyph per cell."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

Pixels = NDArray[np.uint8]
"""A 2D array of 0 (paper) and 1 (ink), indexed `[row, column]`."""


@dataclass(frozen=True)
class Atlas:
    """Glyph cells laid out left to right, top to bottom.

    `grid` atlases separate cells with a 1-pixel line (and start with one), so
    a cell sits at `index * (size + 1) + 1`. Any non-zero pixel is ink.
    """

    pixels: Pixels
    cell_width: int = 8
    cell_height: int = 16
    grid: bool = False

    @classmethod
    def open(cls, path: str | Path, cell_width: int = 8, cell_height: int = 16, grid: bool = False) -> Atlas:
        image = np.array(Image.open(path))
        if image.ndim == 3:
            image = image[..., 0]
        return cls((image != 0).astype(np.uint8), cell_width, cell_height, grid)

    @property
    def columns(self) -> int:
        """Cells per row of the atlas."""
        stride = self.cell_width + 1 if self.grid else self.cell_width
        return int(self.pixels.shape[1] - (1 if self.grid else 0)) // stride

    @property
    def rows(self) -> int:
        stride = self.cell_height + 1 if self.grid else self.cell_height
        return int(self.pixels.shape[0] - (1 if self.grid else 0)) // stride

    def __len__(self) -> int:
        return self.columns * self.rows

    def glyph(self, index: int) -> Pixels:
        """The cell of glyph `index`, `cell_height` x `cell_width`."""
        row, column = divmod(index, self.columns)
        if self.grid:
            x = column * (self.cell_width + 1) + 1
            y = row * (self.cell_height + 1) + 1
        else:
            x = column * self.cell_width
            y = row * self.cell_height
        return self.pixels[y : y + self.cell_height, x : x + self.cell_width]

    def ink_width(self, index: int) -> int:
        """Columns up to and including the rightmost ink pixel (0 for a blank cell)."""
        return ink_width(self.glyph(index))

    def without_grid(self) -> Pixels:
        """The atlas with its grid lines removed: cells packed edge to edge."""
        lines = [
            np.concatenate([self.glyph(row * self.columns + column) for column in range(self.columns)], axis=1)
            for row in range(self.rows)
        ]
        return np.concatenate(lines, axis=0)


def ink_width(glyph: Pixels) -> int:
    """Columns up to and including the rightmost ink pixel of `glyph`."""
    columns = np.flatnonzero(glyph.any(axis=0))
    return int(columns[-1]) + 1 if columns.size else 0


def ink_rows(glyph: Pixels) -> tuple[int, int]:
    """First and last rows holding ink; the whole height for a blank glyph."""
    rows = np.flatnonzero(glyph.any(axis=1))
    if not rows.size:
        return 0, glyph.shape[0] - 1
    return int(rows[0]), int(rows[-1])


def save_png(pixels: Pixels, path: str | Path) -> None:
    """Write 0/1 pixels as a black-on-white PNG."""
    Image.fromarray(np.where(pixels != 0, 0, 255).astype(np.uint8)).save(path, format="PNG")
