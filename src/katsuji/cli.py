"""`katsuji` command line."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from script import Table

from katsuji.atlas import save_png
from katsuji.banner import banner, to_blocks
from katsuji.formats import VwfFont
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    fonts = [VwfFont.decode(path.read_bytes()) for path in args.fonts]
    codes = Table(str(args.table)).to_bytes(args.text)
    pixels = banner(fonts, codes, Controls(font_switch=args.font_switch), kerning=not args.no_kerning)
    if args.png:
        save_png(pixels, args.png)
    else:
        print(to_blocks(pixels))
        print(f"width: {pixels.shape[1]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
