"""Fonts katsuji ships, laid onto any game's text table.

A font is `family/size/style`: `sumi/8/regular`, `sumi/16/bold`. The style
defaults to `regular` (`sumi/16`). Each is a palettized PNG of 8-pixel-wide
cells, 16 per row, and a `charmap.tbl` giving each cell's text (`5E5F=Œ` for a
glyph drawn across two cells); `layout`
moves the glyphs to the codes a game's own table gives the same texts.
"""

import tomllib
from dataclasses import dataclass
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable

from katsuji.atlas import Atlas
from katsuji.remap import Remapped, Span, Target, remap, table_codes

DEFAULT_STYLE = "regular"


@dataclass(frozen=True)
class BundledFont:
    name: str
    atlas: Atlas
    charmap: dict[str, Span]
    """The cells of each text the font draws: one, or several side by side for a glyph wider than a cell."""

    def layout(self, target: Target) -> Remapped:
        """The glyphs at the codes of `target`, a game's table: each code gets its text's glyph, a span of codes
        the glyph cut across them."""
        return remap(self.atlas, self.charmap, target)


def names() -> list[str]:
    """Every bundled font, `family/size/style`."""
    return sorted(
        f"{family.name}/{size.name}/{style.name}"
        for family in _folders(files(__package__))
        for size in _folders(family)
        for style in _folders(size)
    )


def bundled(name: str) -> BundledFont:
    """The bundled font `name`, `family/size[/style]`."""
    folder = _folder(name)
    meta = tomllib.loads(folder.joinpath("font.toml").read_text(encoding="utf-8"))
    width, height = meta["cell"]
    with as_file(folder.joinpath("glyphs.png")) as png:
        atlas = Atlas.open(png, width, height)
    with as_file(folder.joinpath("charmap.tbl")) as charmap:
        return BundledFont(name, atlas, table_codes(charmap))


def _folder(name: str) -> Traversable:
    parts = name.split("/")
    if len(parts) == 2:
        parts.append(DEFAULT_STYLE)
    folder = files(__package__).joinpath(*parts) if len(parts) == 3 else None
    if folder is None or not folder.joinpath("charmap.tbl").is_file():
        raise KeyError(f"no bundled font {name!r}; there are {', '.join(names())}")
    return folder


def _folders(parent: Traversable) -> list[Traversable]:
    return [child for child in parent.iterdir() if child.is_dir() and not child.name.startswith("_")]
