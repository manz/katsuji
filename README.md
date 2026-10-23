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

A font the game reads in its own layout instead of katsuji's VWF file takes a `format`:

```toml
[fonts.menu]
format = "tiles"                         # SNES planar tiles of the PNG's colour indices
png = "fonts/menu.png"                   # palettized: index N is colour N
cell = [8, 8]
bpp = 2
output = "build/menu_font.dat"

[fonts.dialog]
format = "rows16"                        # 1bpp rows, 16 pixels wide, little-endian words (FF6)
png = "fonts/dialog.png"
cell = [12, 11]
first = "0x20"                           # codes written: first .. first + count - 1
count = 224
x-offset = 4                             # glyph drawn 4 pixels into the row
spacing = 1                              # width = ink + spacing, then `widths` overrides
size = 0x1400                            # padded to this many bytes
output = "build/dialog_font.dat"
widths-output = "build/dialog_widths.dat"  # one width byte per code
```

```
katsuji remap fonts/menu.png --table old.tbl --to new.tbl --cell 8x8 -o fonts/menu_new.png
```

moves a font's glyphs to the codes another table gives the same texts, keeping a palettized PNG's colours.

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
- `TextLayout` / `TableMeasure`: dialog reflowed to its window; `TableMeasure` measures script text through its
  `.tbl` and font, tags (names) at fixed widths.
- `encode_tiles` / `colourize`: SNES 2bpp / 4bpp planar tiles.
- `text_tiles` / `pack_runs`: static strings pre-rendered to a bank-safe blob.
- `katsuji.script`: `.tbl` text tables (`Table`), pointer tables and their XML (`pointers`), pointer formulas
  (`formulas`, given the bus mapping by the caller). Moved from a816's `script` package; a816 reads its `.table`
  directive through it. Imports neither numpy nor pillow.
- `katsuji.codecs.sdd1`: the S-DD1 decompressor and a compressor whose streams it reads back.
- `katsuji.codecs.lzss`: `Lzss(...)`, one flag-byte LZSS per parameter set (window, reference layout, ring
  buffer, flag order, search, padding); star_ocean's text, dq6's credits and bahamut_lagoon's rooms and
  graphics are such sets.

Grown from ff4's tooling: its five fonts rebuild byte for byte, its wrapping and dialog goldens pass.

```
uv sync
make check
```
