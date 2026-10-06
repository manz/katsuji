# katsuji

活字, movable type. Variable-width font tooling for [a816](https://github.com/manz/a816) SNES projects.

## Build a project's fonts and strings

`katsuji.toml` at the project root:

```toml
[fonts.dialog]
png = "fonts/vwf.png"
cell = [8, 16]
table = "text/ff4fr.tbl"
output = "assets/font.dat"
widths = { "0xFF" = 3, "0xA0" = -1 }     # negative trims, positive sets
kerning-candidates = ["Ta", "Te", "va"]  # tested for collision kerning
kerning = { "tt" = 2 }                   # hand-tuned: pixels tighter

[fonts.menu]
png = "fonts/8x8vwf.png"
cell = [8, 8]
table = "text/ff4_menus.tbl"
output = "assets/menu_font.dat"
constants = "assets/menu_font.i"         # a816 constants describing the file

[strings.items]
font = "menu"
file = "text/items.txt"                  # one string per line (or `texts = [...]`)
bpp = 2
ink = 3
paper = 1
blob = "assets/items_vwf.dat"            # tiles, no string across a bank edge
index = "assets/items_vwf.idx"           # 4 bytes per string: offset lo16, bank, tiles
```

```
katsuji build            # writes every output, paths relative to katsuji.toml
katsuji banner "Tarot" --table text/ff4fr.tbl --font assets/font.dat
```

## Library

- `Atlas`: a font drawn as a PNG grid of cells.
- `find_kerning` / `pair_kerning`: pair kerning by collision (one diagonal touch, never side by side).
- `VwfFont`: the font file the a816 VWF runtime reads (1bpp rows + width per glyph, kerning pairs, height).
- `render` / `measure`: text set at build time exactly as the runtime sets it.
- `Wrapper`: word wrap by pixel width, the game's control codes as data.
- `Window` / `WindowBuilder`: fill text windows; a game's script rules drive them.
- `encode_tiles` / `colourize`: SNES 2bpp / 4bpp planar tiles.
- `text_tiles` / `pack_runs`: static strings pre-rendered to a bank-safe blob.

Grown from ff4's tooling: its five fonts rebuild byte for byte, its wrapping and dialog goldens pass.

```
uv sync
make check
```
