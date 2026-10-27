"""Moving a font between text tables."""

from pathlib import Path

import numpy as np
import pytest

from katsuji.atlas import Atlas, save_png
from katsuji.cli import main
from katsuji.remap import Span, remap, table_codes, table_texts


def _atlas() -> Atlas:
    pixels = np.zeros((16, 16 * 8), dtype=np.uint8)
    pixels[0, 8 * 1] = 1  # glyph 1: "a"
    pixels[1, 8 * 2] = 1  # glyph 2: "b"
    return Atlas(pixels, 8, 16)


def test_table_codes_keep_glyph_entries(tmp_path: Path) -> None:
    path = tmp_path / "t.tbl"
    path.write_text("01=a\n02=b\n2001=あ\n2122=Lv\n03=a\n; comment\n", encoding="utf-8")
    assert table_codes(path) == {"a": (1,), "b": (2,), "あ": (0x20, 0x01)}


def test_a_glyph_moves_to_its_new_code() -> None:
    remapped = remap(_atlas(), {"a": (1,), "b": (2,)}, {0x21: "a", 0x22: "c"})
    assert (remapped.pixels[2 * 16, 1 * 8], remapped.missing) == (1, ["c"])


def test_the_command_writes_the_png(tmp_path: Path) -> None:
    save_png(_atlas().pixels, tmp_path / "font.png")
    (tmp_path / "from.tbl").write_text("01=a\n", encoding="utf-8")
    (tmp_path / "to.tbl").write_text("10=a\n11=z\n", encoding="utf-8")
    out = tmp_path / "out.png"
    args = ["remap", str(tmp_path / "font.png"), "--table", str(tmp_path / "from.tbl")]
    assert main([*args, "--to", str(tmp_path / "to.tbl"), "-o", str(out)]) == 0
    assert Atlas.open(out).glyph(0x10)[0, 0] == 1


def test_table_texts_keeps_every_code(tmp_path: Path) -> None:
    path = tmp_path / "t.tbl"
    path.write_text("01=a\n02=a\nzz=b\n", encoding="utf-8")
    assert table_texts(path) == {(1,): "a", (2,): "a"}


TWO: dict[Span, str] = {(0x10, 0x11): "W"}
KANJI: dict[Span, str] = {(0x20, 0x01): "あ"}


def _wide(ink: int) -> Atlas:
    """Glyph "W" drawn `ink` columns wide from cell 1 on, across cells 1 and 2."""
    pixels = np.zeros((16, 16 * 8), dtype=np.uint8)
    pixels[3, 8 : 8 + ink] = 1
    return Atlas(pixels, 8, 16)


def test_a_wide_glyph_is_cut_across_its_codes() -> None:
    remapped = remap(_wide(12), {"W": (1, 2)}, TWO)
    ink = remapped.pixels[16 + 3, : 2 * 8]
    assert (ink.tolist(), remapped.joins) == ([1] * 12 + [0] * 4, {0x10: 7})


def test_a_narrow_glyph_on_two_codes_advances_as_one() -> None:
    """Each code adds the engine's 1-pixel gap: the cut leaves the total at the ink plus one gap."""
    remapped = remap(_wide(5), {"W": (1, 2)}, TWO)
    first, last = Atlas(remapped.pixels, 8, 16).ink_width(0x10), Atlas(remapped.pixels, 8, 16).ink_width(0x11)
    assert (first, remapped.joins[0x10] + 1 + last + 1) == (4, 5 + 1)


@pytest.mark.parametrize(("ink", "codes"), [(17, (0x10, 0x11)), (9, (0x10,)), (2, (0x10, 0x11))])
def test_a_glyph_its_codes_cannot_hold_is_refused(ink: int, codes: Span) -> None:
    with pytest.raises(ValueError, match="cannot be cut across"):
        remap(_wide(ink), {"W": (1, 2, 3)}, {codes: "W"})


def test_a_span_the_font_lacks_is_not_missing() -> None:
    """A game's two-byte kanji codes are not cells."""
    assert remap(_atlas(), {"a": (1,)}, KANJI).missing == []
