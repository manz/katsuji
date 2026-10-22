"""Variable-width font tooling for a816 SNES projects.

The names below load on first use, so importing a submodule that needs
neither numpy nor pillow does not pull them in.
"""

import sys
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katsuji.atlas import Atlas
    from katsuji.formats import VwfFont
    from katsuji.kerning import find_kerning, pair_kerning
    from katsuji.render import autohint, measure, render, render_colours
    from katsuji.tiles import TileOrder, colourize, encode_tiles
    from katsuji.wrap import Controls, Fixed, Wrapper

_MODULES = {
    "Atlas": "katsuji.atlas",
    "Controls": "katsuji.wrap",
    "Fixed": "katsuji.wrap",
    "TileOrder": "katsuji.tiles",
    "VwfFont": "katsuji.formats",
    "Wrapper": "katsuji.wrap",
    "autohint": "katsuji.render",
    "colourize": "katsuji.tiles",
    "encode_tiles": "katsuji.tiles",
    "find_kerning": "katsuji.kerning",
    "measure": "katsuji.render",
    "pair_kerning": "katsuji.kerning",
    "render": "katsuji.render",
    "render_colours": "katsuji.render",
}

__all__ = [
    "Atlas",
    "Controls",
    "Fixed",
    "TileOrder",
    "VwfFont",
    "Wrapper",
    "autohint",
    "colourize",
    "encode_tiles",
    "find_kerning",
    "measure",
    "pair_kerning",
    "render",
    "render_colours",
]


class _Package(ModuleType):
    """Keeps `katsuji.render` the function: loading the `katsuji.render` module binds it on the package, as the
    import system does for every submodule, and the eager package used to rebind the function over it."""

    def __setattr__(self, name: str, value: object) -> None:
        if isinstance(value, ModuleType) and name in _MODULES:
            return
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _Package


def __getattr__(name: str) -> object:
    module = _MODULES.get(name)
    if module is None:
        raise AttributeError(f"module 'katsuji' has no attribute {name!r}")
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return __all__
