"""`katsuji` command line."""

import argparse
import sys
from collections.abc import Sequence
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


def _code(value: str) -> int:
    return int(value, 0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="katsuji", description="Variable-width font tooling for a816 projects.")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("banner", help="show text set with katsuji fonts")
    show.add_argument("text")
    show.add_argument("--table", required=True, type=Path, help="text table (.tbl) encoding TEXT")
    show.add_argument(
        "--font", required=True, action="append", type=Path, dest="fonts", help="font file; repeat for font switches"
    )
    show.add_argument("--font-switch", type=_code, help="code switching font, followed by the font index (ff4: 0xFE)")
    show.add_argument("--no-kerning", action="store_true", help="ignore the fonts' kerning pairs")
    show.add_argument("--png", type=Path, help="save the banner as a PNG instead of printing it")
    show.add_argument(
        "--auto",
        action="store_true",
        help="FONT is a PNG atlas: measure widths and kern each pair on the glyphs, keeping its colours",
    )
    show.add_argument("--cell", default="8x16", help="with --auto, the atlas's cell size, WIDTHxHEIGHT")
    show.add_argument(
        "--ink", type=_code, action="append", help="with --auto, a colour to measure and kern on (repeat); default: all"
    )
    make = commands.add_parser("build", help="build the fonts and strings a katsuji.toml describes")
    make.add_argument("config", nargs="?", type=Path, default=Path("katsuji.toml"))
    move = commands.add_parser("remap", help="move a font PNG from one text table's codes to another's")
    move.add_argument("png", type=Path, help="the font: a grid of fixed-size cells, glyph N in cell N")
    move.add_argument("--table", required=True, type=Path, help="the table (.tbl) the font is laid out for")
    move.add_argument("--to", required=True, type=Path, dest="target", help="the table (.tbl) to lay it out for")
    move.add_argument("--cell", default="8x16", help="cell size, WIDTHxHEIGHT (default 8x16)")
    move.add_argument("-o", "--output", required=True, type=Path, help="the PNG to write")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
    pixels = autohint(atlas, codes, ink=args.ink)
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


if __name__ == "__main__":
    raise SystemExit(main())
