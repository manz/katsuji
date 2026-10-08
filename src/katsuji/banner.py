"""Banners: text set with katsuji fonts, shown in the terminal or saved as a PNG.

A preview of what the runtime will draw, font switches included. Each run of
text between font switches is set with its font and the runs are joined edge
to edge, as ff4's banner did.
"""

import dataclasses
from collections.abc import Sequence

import numpy as np

from katsuji.atlas import Pixels
from katsuji.formats import VwfFont
from katsuji.render import render
from katsuji.wrap import Controls


def runs(codes: bytes, controls: Controls) -> list[tuple[int, list[int]]]:
    """`codes` split at font switches into `(font, glyph codes)`; fixed codes are skipped."""
    out: list[tuple[int, list[int]]] = []
    font = 0
    current: list[int] = []
    index = 0
    while index < len(codes):
        code = codes[index]
        if code == controls.font_switch and index + 1 < len(codes):
            if current:
                out.append((font, current))
                current = []
            index += 1
            font = codes[index]
        elif code in controls.fixed:
            index += controls.fixed[code].arguments
        else:
            current.append(code)
        index += 1
    if current:
        out.append((font, current))
    return out


def banner(fonts: Sequence[VwfFont], codes: bytes, controls: Controls, kerning: bool = True) -> Pixels:
    """The pixels of `codes`, each run set with its font."""
    pieces = []
    for font_index, glyphs in runs(codes, controls):
        font = fonts[font_index] if kerning else dataclasses.replace(fonts[font_index], kerning={})
        pieces.append(render(font, glyphs))
    if not pieces:
        return np.zeros((0, 0), dtype=np.uint8)
    height = max(piece.shape[0] for piece in pieces)
    return np.concatenate([np.pad(piece, ((0, height - piece.shape[0]), (0, 0))) for piece in pieces], axis=1)


def to_blocks(pixels: Pixels) -> str:
    """Two full blocks per ink pixel, two spaces per paper pixel."""
    return "\n".join("".join("██" if value else "  " for value in row) for row in pixels)
