# katsuji

活字, movable type. Variable-width font tooling for [a816](https://github.com/manz/a816) SNES projects:

- `Atlas`: a font drawn as a PNG grid of cells.
- `find_kerning` / `pair_kerning`: pair kerning found by collision (one diagonal touch, never side by side).
- `VwfFont`: the font file the a816 VWF runtime reads (1bpp rows + width per glyph, kerning pairs, height).
- `render` / `measure`: text set at build time exactly as the runtime sets it.
- `encode_tiles` / `colourize`: SNES 2bpp / 4bpp planar tiles.

Grown from ff4's `utils/font_converter.py`; ff4's five fonts rebuild byte for byte (`tests/test_ff4_fonts.py`).

```
uv sync
uv run pytest
```
