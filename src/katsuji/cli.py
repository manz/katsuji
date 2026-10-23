"""`katsuji` command line. The commands render fonts: their modules load only once one runs, so a text-only install
(no `render` extra) still imports `katsuji` and `katsuji.script`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


def _code(value: str) -> int:
    return int(value, 0)


def _width(value: str) -> tuple[int, int]:
    code, sep, pixels = value.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"{value!r} is not CODE=PX")
    return int(code, 0), int(pixels, 0)


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
    show.add_argument(
        "--width",
        type=_width,
        action="append",
        default=[],
        dest="widths",
        help="with --auto, CODE=PX: set a glyph's width (negative trims), e.g. 0x00=3 for a space; repeat",
    )
    show.add_argument(
        "--avoid", type=_code, action="append", default=[], help="with --auto, a code never kerned (repeat)"
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
    try:
        from katsuji import commands
    except ModuleNotFoundError as missing:
        print(
            f"katsuji: the command line renders fonts and needs {missing.name}: install katsuji[render]",
            file=sys.stderr,
        )
        return 2
    return commands.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
