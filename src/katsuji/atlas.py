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
    a cell sits at `index * (size + 1) + 1`. Any non-zero pixel is ink: palette
    index 1 in a palettized PNG (what `save_png` writes), light on dark otherwise.

    A palettized PNG also keeps its colour indices (`colours`, `palette`), for
    fonts drawn in more than ink and paper: a 2bpp menu font's shadows.
    """

    pixels: Pixels
    cell_width: int = 8
    cell_height: int = 16
    grid: bool = False
    colours: Pixels | None = None
    """The palette index of every pixel, when the PNG is palettized."""
    palette: tuple[int, ...] | None = None
    """That PNG's palette, flat RGB triples."""

    @classmethod
    def open(cls, path: str | Path, cell_width: int = 8, cell_height: int = 16, grid: bool = False) -> Atlas:
        with Image.open(path) as png:
            palette = tuple(png.getpalette() or ()) if png.mode == "P" else None
            image = np.array(png)
        if image.ndim == 3:
            image = image[..., 0]
        colours = image.astype(np.uint8) if palette is not None else None
        return cls((image != 0).astype(np.uint8), cell_width, cell_height, grid, colours, palette)

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
        return self._cell(self.pixels, index)

    def glyph_colours(self, index: int) -> Pixels:
        """The colour indices of glyph `index`'s cell; its ink (1) and paper (0) when the PNG has no palette."""
        return self._cell(self.pixels if self.colours is None else self.colours, index)

    def _cell(self, pixels: Pixels, index: int) -> Pixels:
        row, column = divmod(index, self.columns)
        if self.grid:
            x = column * (self.cell_width + 1) + 1
            y = row * (self.cell_height + 1) + 1
        else:
            x = column * self.cell_width
            y = row * self.cell_height
        return pixels[y : y + self.cell_height, x : x + self.cell_width]

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


def save_png(pixels: Pixels, path: str | Path, palette: tuple[int, ...] | None = None) -> None:
    """Write a palettized PNG that `Atlas.open` reads back. Without `palette`: 0/1 pixels, index 0 paper, 1 ink,
    shown black on white. With one: `pixels` are colour indices into it."""
    if palette is None:
        image = Image.fromarray((pixels != 0).astype(np.uint8), mode="P")
        image.putpalette([255, 255, 255, 0, 0, 0])
    else:
        image = Image.fromarray(pixels.astype(np.uint8), mode="P")
        image.putpalette(list(palette))
    image.save(path, format="PNG")
