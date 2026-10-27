"""`katsuji.fonts`: the sumi faces, and `builtin = ...` laying one onto a game's table."""

import unicodedata
from pathlib import Path

import numpy as np
import pytest

from katsuji.atlas import Atlas, ink_width, save_png
from katsuji.build import build
from katsuji.config import ConfigError, load
from katsuji.fonts import bundled, names
from katsuji.formats import VwfFont, pack_rows
from katsuji.remap import Span


def test_sumi_ships_two_sizes_and_four_styles() -> None:
    assert names() == ["sumi/16/bold", "sumi/16/book", "sumi/16/regular", "sumi/16/wicked", "sumi/8/regular"]


def test_a_size_alone_is_its_regular_style() -> None:
    assert bundled("sumi/16").atlas.glyph(5).tobytes() == bundled("sumi/16/regular").atlas.glyph(5).tobytes()


@pytest.mark.parametrize(("name", "height"), [("sumi/8", 8), ("sumi/16/bold", 16)])
def test_a_font_knows_its_cell(name: str, height: int) -> None:
    assert bundled(name).atlas.cell_height == height


@pytest.mark.parametrize("name", ["sumi", "sumi/12", "mincho/16", "sumi/16/italic/x"])
def test_an_unknown_font_lists_the_bundled_ones(name: str) -> None:
    with pytest.raises(KeyError, match="there are sumi/16/bold"):
        bundled(name)


def test_curly_quotes_draw_the_quote_in_regular() -> None:
    charmap = bundled("sumi/16").charmap
    assert (charmap["“"], charmap["”"]) == (charmap['"'], charmap['"'])


def test_layout_puts_a_glyph_at_the_game_code() -> None:
    font = bundled("sumi/16")
    laid = font.layout({0x41: "é"})
    assert np.array_equal(laid.pixels[64:80, 8:16], font.atlas.glyph_colours(font.charmap["é"]))


def test_layout_reports_texts_the_font_lacks() -> None:
    assert bundled("sumi/8").layout({1: "A", 0: "<END>"}).missing == ["<END>"]


def _builtin(tmp_path: Path, table: str, extra: str = "") -> Path:
    (tmp_path / "game.tbl").write_text(table, encoding="utf-8")
    path = tmp_path / "katsuji.toml"
    path.write_text(
        f"[fonts.f]\nbuiltin = 'sumi/8'\ntable = 'game.tbl'\noutput = 'f.dat'\nwidths = {{ '0x00' = 3 }}\n{extra}",
        encoding="utf-8",
    )
    return path


def _font(tmp_path: Path) -> VwfFont:
    return VwfFont.decode((tmp_path / "f.dat").read_bytes())


def test_a_builtin_font_lands_on_the_table_codes(tmp_path: Path) -> None:
    build(load(_builtin(tmp_path, "00= \n10=A\n11=é\nFF=<END>\n")))
    sumi = bundled("sumi/8")
    assert _font(tmp_path).glyphs[0x11] == VwfFont.from_atlas(sumi.atlas).glyphs[sumi.charmap["é"]]


def test_a_text_the_builtin_lacks_must_be_drawn(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"sumi/8 draws no '\$': draw them in `overrides`"):
        build(load(_builtin(tmp_path, "10=A\n11=$\n")))


def test_an_accented_capital_sumi_8_lacks_draws_its_base_letter(tmp_path: Path) -> None:
    """A table shared by an 8x8 and a 16-pixel font keeps É: the 8x8 cell shows E."""
    build(load(_builtin(tmp_path, "10=E\n11=É\n")))
    glyphs = _font(tmp_path).glyphs
    assert glyphs[0x11] == glyphs[0x10]


def test_the_base_letter_comes_from_the_font_not_the_table(tmp_path: Path) -> None:
    build(load(_builtin(tmp_path, "10=A\n11=É\n")))
    sumi = bundled("sumi/8")
    assert _font(tmp_path).glyphs[0x11] == VwfFont.from_atlas(sumi.atlas).glyphs[sumi.charmap["E"]]


def test_overrides_win_over_the_base_letter(tmp_path: Path) -> None:
    icons = np.zeros((128, 128), np.uint8)
    icons[8:16, 8:12] = 1  # code 0x11
    save_png(icons, tmp_path / "icons.png")
    build(load(_builtin(tmp_path, "10=E\n11=É\n", "overrides = 'icons.png'\n")))
    assert _font(tmp_path).glyphs[0x11] == pack_rows(icons[8:16, 8:16])


def test_sumi_8_draws_no_accented_capitals() -> None:
    """An 8x8 cell has no room for them: the cell shows the base letter, and encoding writes it when the table
    leaves them out."""
    assert not {
        text for text in bundled("sumi/8").charmap if text.isupper() and unicodedata.normalize("NFD", text) != text
    }


def test_a_glyph_on_two_codes_advances_as_one(tmp_path: Path) -> None:
    """ff4's `A0A1=œ`: sumi's wide œ is laid across both codes, the first narrowed to join."""
    build(load(_builtin(tmp_path, "10=A\nA0A1=œ\n")))
    widths = _font(tmp_path).widths
    sumi = bundled("sumi/8")
    wide = np.hstack([sumi.atlas.glyph(code) for code in sumi.wide["œ"]])
    assert widths[0xA0] + 1 + widths[0xA1] + 1 == ink_width(wide) + 1


@pytest.mark.parametrize("name", names())
def test_a_span_gets_the_wide_drawing_and_one_code_the_narrow(name: str) -> None:
    font = bundled(name)
    width = font.atlas.cell_width
    target: dict[Span, str] = {(0x10,): "œ", (0x20, 0x21): "œ"}
    remapped = font.layout(target)
    laid = Atlas(remapped.pixels, width, font.atlas.cell_height)
    wide = np.hstack([font.atlas.glyph(code) for code in font.wide["œ"]])
    assert (laid.ink_width(0x10), remapped.joins[0x20] + 1 + laid.ink_width(0x21)) == (
        font.atlas.ink_width(font.charmap["œ"]),
        ink_width(wide),
    )


@pytest.mark.parametrize("name", [name for name in names() if not name.endswith("/regular")])
def test_every_style_draws_wide_what_regular_draws_wide(name: str) -> None:
    regular = name.rsplit("/", 1)[0]
    assert set(bundled(name).wide) == set(bundled(regular).wide)


def test_a_game_width_on_a_joined_code_wins(tmp_path: Path) -> None:
    (tmp_path / "game.tbl").write_text("10=A\nA0A1=œ\n", encoding="utf-8")
    (tmp_path / "katsuji.toml").write_text(
        "[fonts.f]\nbuiltin = 'sumi/8'\ntable = 'game.tbl'\noutput = 'f.dat'\nwidths = { '0xA0' = 5 }\n",
        encoding="utf-8",
    )
    build(load(tmp_path / "katsuji.toml"))
    assert _font(tmp_path).widths[0xA0] == 5


def test_a_latin_run_the_builtin_lacks_must_be_drawn(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"draws no '@'"):
        build(load(_builtin(tmp_path, "10=A\nA0A1=@\n")))


def test_two_byte_codes_the_font_lacks_build(tmp_path: Path) -> None:
    build(load(_builtin(tmp_path, "10=A\n2001=あ\n")))
    assert _font(tmp_path).widths[0x20] == 0


def test_a_width_below_zero_is_a_config_error(tmp_path: Path) -> None:
    (tmp_path / "game.tbl").write_text("10=A\n", encoding="utf-8")
    (tmp_path / "katsuji.toml").write_text(
        "[fonts.f]\nbuiltin = 'sumi/8'\ntable = 'game.tbl'\noutput = 'f.dat'\nwidths = { '0x11' = -1 }\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match=r"trims 0x11 by more than their measured width"):
        build(load(tmp_path / "katsuji.toml"))


def test_a_glyph_too_wide_for_its_code_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot be cut across"):
        build(load(_builtin(tmp_path, "10=A\nA0A1A2=.\n")))


def test_overrides_draw_the_cells_the_builtin_lacks(tmp_path: Path) -> None:
    icons = np.zeros((128, 128), np.uint8)
    icons[8:16, 8:16] = 1  # code 0x11
    save_png(icons, tmp_path / "icons.png")
    build(load(_builtin(tmp_path, "10=A\n11=$\n", "overrides = 'icons.png'\n")))
    assert _font(tmp_path).glyphs[0x11] == pack_rows(icons[8:16, 8:16])


def test_a_blank_code_builds_empty(tmp_path: Path) -> None:
    """ff4's `FD=°` is a 1-pixel spacer, not a degree sign."""
    build(load(_builtin(tmp_path, "10=A\nFD=°\n", "blank = ['0xFD']\n")))
    glyph = _font(tmp_path).glyphs[0xFD]
    assert glyph == bytes(len(glyph))


def test_a_blank_code_stays_empty_where_the_builtin_draws(tmp_path: Path) -> None:
    build(load(_builtin(tmp_path, "10=A\n11=B\n", "blank = [0x11]\n")))
    glyph = _font(tmp_path).glyphs[0x11]
    assert glyph == bytes(len(glyph))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("builtin = 'sumi/8'\npng = 'f.png'\ntable = 't'\n", "needs one of `png` or `builtin`"),
        ("builtin = 'sumi/8'\n", "`builtin` needs the `table`"),
        ("builtin = 'sumi/8'\ntable = 't'\ncell = [8, 8]\n", "set their own cell"),
        ("png = 'f.png'\noverrides = 'o.png'\n", "`overrides` goes with `builtin`"),
        ("png = 'f.png'\nblank = ['0xFD']\n", "`blank` goes with `builtin`"),
    ],
)
def test_builtin_config_errors(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "katsuji.toml"
    path.write_text(f"[fonts.f]\noutput = 'f.dat'\n{text}", encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load(path)


def test_an_unknown_builtin_is_a_config_error(tmp_path: Path) -> None:
    path = tmp_path / "katsuji.toml"
    path.write_text("[fonts.f]\nbuiltin = 'sumi/9'\ntable = 'g.tbl'\noutput = 'f.dat'\n", encoding="utf-8")
    (tmp_path / "g.tbl").write_text("10=A\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"\[fonts.f\] no bundled font 'sumi/9'"):
        build(load(path))


def test_every_code_of_a_text_gets_its_glyph(tmp_path: Path) -> None:
    build(load(_builtin(tmp_path, "10=A\n11=A\n")))
    glyphs = _font(tmp_path).glyphs
    assert glyphs[0x11] == glyphs[0x10] != bytes(len(glyphs[0x10]))


@pytest.mark.parametrize("name", [name for name in names() if not name.endswith("/regular")])
def test_every_style_draws_what_regular_draws(name: str) -> None:
    """A game swaps styles without its table gaining blank cells."""
    regular = name.rsplit("/", 1)[0]
    assert set(bundled(name).charmap) == set(bundled(regular).charmap)
