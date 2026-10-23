"""The `katsuji` commands: everything here renders, so it needs the `render` extra (numpy, pillow)."""

import argparse
import sys
from pathlib import Path

from katsuji.atlas import Atlas, save_png
from katsuji.banner import banner, to_blocks
from katsuji.build import build
from katsuji.config import ConfigError, load
from katsuji.formats import VwfFont
from katsuji.remap import remap, table_codes
from katsuji.render import autohint
from katsuji.script import Table
from katsuji.wrap import Controls


def run(args: argparse.Namespace) -> int:
    if args.command == "build":
        return _build(args.config)
    if args.command == "remap":
        return _remap(args)
    codes = Table(str(args.table)).to_bytes(args.text)
    if args.auto:
        return _auto(args, codes)
    fonts = [VwfFont.decode(path.read_bytes()) for path in args.fonts]
    pixels = banner(fonts, codes, Controls(font_switch=args.font_switch), kerning=not args.no_kerning)
    if args.png:
        save_png(pixels, args.png)
    else:
        print(to_blocks(pixels))
        print(f"width: {pixels.shape[1]}", file=sys.stderr)
    return 0


def _auto(args: argparse.Namespace, codes: bytes) -> int:
    width, _, height = str(args.cell).partition("x")
    atlas = Atlas.open(args.fonts[0], int(width), int(height))
    pixels = autohint(atlas, codes, ink=args.ink, widths=dict(args.widths), avoid=args.avoid)
    if args.png:
        save_png(pixels, args.png, atlas.palette or _greys(int(pixels.max(initial=1))))
    else:
        print(to_blocks(pixels))
        print(f"width: {pixels.shape[1]}", file=sys.stderr)
    return 0


def _greys(top: int) -> tuple[int, ...]:
    """Paper white, then evenly darker greys up to colour `top` black."""
    return tuple(value for level in range(top + 1) for value in (255 - 255 * level // top,) * 3)


def _remap(args: argparse.Namespace) -> int:
    width, _, height = str(args.cell).partition("x")
    atlas = Atlas.open(args.png, int(width), int(height))
    remapped = remap(atlas, table_codes(args.table), table_codes(args.target))
    save_png(remapped.pixels, args.output, remapped.palette)
    print(args.output)
    if remapped.missing:
        print(f"not in the font: {' '.join(remapped.missing)}", file=sys.stderr)
    return 0


def _build(path: Path) -> int:
    try:
        for written in build(load(path)):
            print(written)
    except ConfigError as error:
        print(f"katsuji: {error}", file=sys.stderr)
        return 2
    return 0
