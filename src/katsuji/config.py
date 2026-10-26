"""`katsuji.toml`: the fonts and static strings a project builds.

```toml
[fonts.dialog]
png = "fonts/vwf.png"
cell = [8, 16]                  # width, height of a glyph cell
table = "text/ff4fr.tbl"        # .tbl encoding the kerning candidates and strings
output = "assets/font.dat"
widths = { "0xFF" = 3, "0xA0" = -1 }   # negative: trim, positive: set
kerning-candidates = ["Ta", "Te"]      # pairs to test for collision kerning
kerning = { "tt" = 2 }                 # hand-tuned pairs: pixels tighter

[fonts.menu]                    # a font the game reads as its own layout (see katsuji.tile_fonts)
format = "tiles"                # or "rows16" (16-pixel 1bpp rows, widths written apart); default "vwf"
png = "fonts/menu.png"          # palettized: the cells' colour indices are the tiles' colours
cell = [8, 8]
bpp = 2
first = "0x00"                  # first code written, then `count` glyphs
output = "build/menu_font.dat"
size = 0x1000                   # pad the file to this many bytes

[strings.items]
font = "menu"
texts = ["Potion", "Ether"]     # or `file = "text/items.txt"`, one per line
bpp = 2
ink = 3
paper = 1
blob = "assets/items_vwf.dat"
index = "assets/items_vwf.idx"
```

Both tables take `constants = "path.i"`: a816 constants describing the output.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """`katsuji.toml` is invalid; the message names the table and key."""


@dataclass(frozen=True)
class FontConfig:
    name: str
    png: Path | None
    """The font's own atlas; None when it is `builtin`."""
    output: Path
    table: Path | None = None
    cell_width: int = 8
    cell_height: int = 16
    grid: bool = False
    widths: dict[int, int] = field(default_factory=dict)
    kerning_candidates: tuple[str, ...] = ()
    kerning: dict[str, int] = field(default_factory=dict)
    default_kerning: int = 1
    constants: Path | None = None
    format: str = "vwf"
    """`vwf` (katsuji's VWF file), `tiles` or `rows16` (see `katsuji.tile_fonts`)."""
    bpp: int = 2
    first: int = 0
    count: int = 256
    x_offset: int = 0
    spacing: int = 0
    size: int | None = None
    widths_output: Path | None = None
    builtin: str | None = None
    """A font katsuji ships (`katsuji.fonts`), laid onto `table`."""
    overrides: Path | None = None
    """An atlas on `table`'s codes whose drawn cells replace the builtin's: icons, game-only glyphs."""


FORMATS = ("vwf", "tiles", "rows16")


@dataclass(frozen=True)
class StringsConfig:
    name: str
    font: str
    blob: Path
    index: Path
    texts: tuple[str, ...]
    bpp: int = 2
    ink: int = 3
    paper: int = 1
    gap: int = 1
    max_tiles: int | None = None
    bank_size: int = 0x10000
    table: Path | None = None
    constants: Path | None = None


@dataclass(frozen=True)
class Config:
    fonts: dict[str, FontConfig]
    strings: dict[str, StringsConfig]


_COMMON_FONT_KEYS = {"png", "output", "table", "cell", "grid", "widths", "format"}
_FONT_KEYS = {
    "vwf": _COMMON_FONT_KEYS
    | {"kerning-candidates", "kerning", "default-kerning", "constants", "builtin", "overrides"},
    "tiles": _COMMON_FONT_KEYS | {"bpp", "first", "count", "size"},
    "rows16": _COMMON_FONT_KEYS | {"first", "count", "size", "x-offset", "spacing", "widths-output"},
}
_STRING_KEYS = {"font", "blob", "index", "texts", "file", "bpp", "ink", "paper", "gap", "max-tiles", "bank-size"}
_STRING_KEYS |= {"table", "constants"}


def load(path: Path) -> Config:
    """Read `path`; relative paths in it resolve against its directory."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error
    unknown = set(data) - {"fonts", "strings"}
    if unknown:
        raise ConfigError(f"{path}: unknown table(s) {sorted(unknown)}; expected [fonts.NAME] and [strings.NAME]")
    root = path.parent
    fonts = {name: _font(name, table, root) for name, table in data.get("fonts", {}).items()}
    strings = {name: _strings(name, table, root) for name, table in data.get("strings", {}).items()}
    for strings_config in strings.values():
        if strings_config.font not in fonts:
            raise ConfigError(f"[strings.{strings_config.name}] font {strings_config.font!r} is not a [fonts.NAME]")
    return Config(fonts, strings)


def _check_keys(where: str, table: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    unknown = set(table) - allowed
    if unknown:
        raise ConfigError(f"[{where}] unknown key(s) {sorted(unknown)}")
    missing = required - set(table)
    if missing:
        raise ConfigError(f"[{where}] missing key(s) {sorted(missing)}")


def _path(root: Path, value: str | None) -> Path | None:
    return None if value is None else root / value


def _font(name: str, table: dict[str, Any], root: Path) -> FontConfig:
    where = f"fonts.{name}"
    kind = table.get("format", "vwf")
    if kind not in FORMATS:
        raise ConfigError(f"[{where}] format {kind!r} is not one of {', '.join(FORMATS)}")
    _check_keys(where, table, _FONT_KEYS[kind], {"output"})
    _check_source(where, table)
    if kind == "rows16" and "widths-output" not in table:
        raise ConfigError(f"[{where}] format 'rows16' needs `widths-output`")
    width, height = table.get("cell", [8, 16])
    return FontConfig(
        name=name,
        png=_path(root, table.get("png")),
        output=root / table["output"],
        table=_path(root, table.get("table")),
        cell_width=width,
        cell_height=height,
        grid=table.get("grid", False),
        widths={_code(where, key): value for key, value in table.get("widths", {}).items()},
        kerning_candidates=tuple(table.get("kerning-candidates", ())),
        kerning=dict(table.get("kerning", {})),
        default_kerning=table.get("default-kerning", 1),
        constants=_path(root, table.get("constants")),
        format=kind,
        bpp=table.get("bpp", 2),
        first=_code(where, str(table.get("first", 0))),
        count=table.get("count", 256),
        x_offset=table.get("x-offset", 0),
        spacing=table.get("spacing", 0),
        size=table.get("size"),
        widths_output=_path(root, table.get("widths-output")),
        builtin=table.get("builtin"),
        overrides=_path(root, table.get("overrides")),
    )


def _check_source(where: str, table: dict[str, Any]) -> None:
    """A font draws from its own `png` or a `builtin` one laid onto its `table`."""
    if ("png" in table) == ("builtin" in table):
        raise ConfigError(f"[{where}] needs one of `png` or `builtin`")
    if "builtin" not in table:
        if "overrides" in table:
            raise ConfigError(f"[{where}] `overrides` goes with `builtin`")
        return
    if "table" not in table:
        raise ConfigError(f"[{where}] `builtin` needs the `table` to lay it onto")
    clashing = {"cell", "grid"} & set(table)
    if clashing:
        raise ConfigError(f"[{where}] `builtin` fonts set their own {', '.join(sorted(clashing))}")


def _strings(name: str, table: dict[str, Any], root: Path) -> StringsConfig:
    where = f"strings.{name}"
    _check_keys(where, table, _STRING_KEYS, {"font", "blob", "index"})
    if ("texts" in table) == ("file" in table):
        raise ConfigError(f"[{where}] give exactly one of `texts` and `file`")
    if "texts" in table:
        texts = tuple(table["texts"])
    else:
        texts = tuple(line for line in (root / table["file"]).read_text(encoding="utf-8").splitlines() if line)
    return StringsConfig(
        name=name,
        font=table["font"],
        blob=root / table["blob"],
        index=root / table["index"],
        texts=texts,
        bpp=table.get("bpp", 2),
        ink=table.get("ink", 3),
        paper=table.get("paper", 1),
        gap=table.get("gap", 1),
        max_tiles=table.get("max-tiles"),
        bank_size=table.get("bank-size", 0x10000),
        table=_path(root, table.get("table")),
        constants=_path(root, table.get("constants")),
    )


def _code(where: str, key: str) -> int:
    try:
        return int(key, 0)
    except ValueError as error:
        raise ConfigError(f'[{where}] {key!r} is not a code (write it like "0xFF")') from error
