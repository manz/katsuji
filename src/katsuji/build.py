"""Build everything a `katsuji.toml` describes: font files, string blobs, constants."""

from pathlib import Path

import numpy as np

from katsuji.atlas import Atlas
from katsuji.config import Config, ConfigError, FontConfig, StringsConfig
from katsuji.formats import VwfFont
from katsuji.kerning import find_kerning
from katsuji.remap import table_texts
from katsuji.script import Table
from katsuji.strings import index_entry, pack_runs, text_tiles
from katsuji.tile_fonts import encode_rows16_font, encode_tile_font, rows16_widths


def build(config: Config) -> list[Path]:
    """Write every output of `config`; returns the paths written."""
    written: list[Path] = []
    fonts: dict[str, VwfFont] = {}
    for name, font in config.fonts.items():
        if font.format == "vwf":
            fonts[name] = _build_font(font, written)
        else:
            _build_tile_font(font, written)
    for strings in config.strings.values():
        if strings.font not in fonts:
            raise ConfigError(f"[strings.{strings.name}] font {strings.font!r} is not a 'vwf' font")
        _build_strings(strings, fonts[strings.font], config.fonts[strings.font], written)
    return written


def _table(path: Path | None, where: str) -> Table:
    if path is None:
        raise ConfigError(f"[{where}] needs a `table` to encode its text")
    return Table(str(path))


def _pair(table: Table, text: str, where: str) -> tuple[int, int]:
    codes = table.to_bytes(text)
    if len(codes) != 2:
        raise ConfigError(f"[{where}] kerning pair {text!r} encodes to {len(codes)} codes, not 2")
    return codes[0], codes[1]


def _build_font(config: FontConfig, written: list[Path]) -> VwfFont:
    where = f"fonts.{config.name}"
    atlas = _atlas(config, where)
    kerning: dict[tuple[int, int], int] = {}
    if config.kerning_candidates or config.kerning:
        table = _table(config.table, where)
        candidates = (table.to_bytes(text) for text in config.kerning_candidates)
        pairs = [(codes[0], codes[1]) for codes in candidates if len(codes) == 2]
        kerning = find_kerning(atlas, pairs, config.default_kerning)
        for text, pixels in config.kerning.items():
            kerning[_pair(table, text, where)] = pixels
    font = VwfFont.from_atlas(atlas, config.widths, kerning)
    _write(config.output, font.encode(), written)
    if config.constants:
        prefix = config.name.upper()
        _write_constants(
            config.constants,
            {
                f"{prefix}_FONT_HEIGHT": font.height,
                f"{prefix}_FONT_GLYPH_SIZE": font.height + 1,
                f"{prefix}_FONT_KERNING_PAIRS": len(font.kerning),
            },
            written,
        )
    return font


def _atlas(config: FontConfig, where: str) -> Atlas:
    if config.builtin is None:
        assert config.png is not None  # config.load requires one of them
        return Atlas.open(config.png, config.cell_width, config.cell_height, config.grid)
    return _builtin_atlas(config, where)


def _builtin_atlas(config: FontConfig, where: str) -> Atlas:
    """The builtin font on `table`'s codes, the drawn cells of `overrides` on top.
    A one-character text neither draws is an error; a blank or a control is not."""
    from katsuji.fonts import bundled

    assert config.builtin is not None and config.table is not None  # config.load checks both
    try:
        font = bundled(config.builtin)
    except KeyError as error:
        raise ConfigError(f"[{where}] {error.args[0]}") from error
    target = table_texts(config.table)
    laid = font.layout(target)
    width, height = font.atlas.cell_width, font.atlas.cell_height
    atlas = Atlas((laid.pixels != 0).astype(np.uint8), width, height, colours=laid.pixels, palette=laid.palette)
    if config.overrides is not None:
        atlas = _overlay(atlas, Atlas.open(config.overrides, width, height))
    undrawn = sorted(
        {text for code, text in target.items() if len(text) == 1 and not text.isspace() and not atlas.glyph(code).any()}
    )
    if undrawn:
        raise ConfigError(f"[{where}] {config.builtin} draws no {''.join(undrawn)!r}: draw them in `overrides`")
    return atlas


def _overlay(atlas: Atlas, overrides: Atlas) -> Atlas:
    """`atlas` with each cell `overrides` draws replaced by it."""
    pixels = atlas.colours.copy() if atlas.colours is not None else atlas.pixels.copy()
    for index in range(min(len(atlas), len(overrides))):
        cell = overrides.glyph_colours(index)
        if cell.any():
            row, column = divmod(index, atlas.columns)
            h, w = atlas.cell_height, atlas.cell_width
            pixels[row * h : (row + 1) * h, column * w : (column + 1) * w] = cell
    return Atlas(
        (pixels != 0).astype(np.uint8), atlas.cell_width, atlas.cell_height, colours=pixels, palette=atlas.palette
    )


def _build_tile_font(config: FontConfig, written: list[Path]) -> None:
    atlas = _atlas(config, f"fonts.{config.name}")
    if config.format == "tiles":
        data = encode_tile_font(atlas, config.bpp, config.first, config.count, config.size)
    else:
        data = encode_rows16_font(atlas, config.x_offset, config.first, config.count, config.size)
        assert config.widths_output is not None  # config.load requires it for rows16
        widths = rows16_widths(atlas, config.spacing, config.widths, config.first, config.count)
        _write(config.widths_output, widths, written)
    _write(config.output, data, written)


def _build_strings(config: StringsConfig, font: VwfFont, font_config: FontConfig, written: list[Path]) -> None:
    where = f"strings.{config.name}"
    table = _table(config.table or font_config.table, where)
    runs: list[bytes] = []
    counts: list[int] = []
    for text in config.texts:
        tiles, columns = text_tiles(
            font, table.to_bytes(text), config.bpp, config.ink, config.paper, config.gap, config.max_tiles
        )
        runs.append(tiles)
        counts.append(columns)
    blob, offsets = pack_runs(runs, config.bank_size)
    _write(config.blob, blob, written)
    _write(config.index, b"".join(index_entry(o, n) for o, n in zip(offsets, counts, strict=True)), written)
    if config.constants:
        prefix = config.name.upper()
        _write_constants(
            config.constants,
            {f"{prefix}_COUNT": len(config.texts), f"{prefix}_MAX_TILES": max(counts, default=0)},
            written,
        )


def _write(path: Path, data: bytes, written: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    written.append(path)


def _write_constants(path: Path, constants: dict[str, int], written: list[Path]) -> None:
    lines = ['"""Generated by katsuji build; do not edit."""', ""]
    lines += [f"{name} = {value:#x}" if value > 9 else f"{name} = {value}" for name, value in constants.items()]
    _write(path, ("\n".join(lines) + "\n").encode(), written)
