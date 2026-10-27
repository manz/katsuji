"""Moving a font between text tables."""

from pathlib import Path

import numpy as np

from katsuji.atlas import Atlas, save_png
from katsuji.cli import main
from katsuji.remap import remap, table_codes, table_texts


def _atlas() -> Atlas:
    pixels = np.zeros((16, 16 * 8), dtype=np.uint8)
    pixels[0, 8 * 1] = 1  # glyph 1: "a"
    pixels[1, 8 * 2] = 1  # glyph 2: "b"
    return Atlas(pixels, 8, 16)


def test_table_codes_keep_one_byte_entries(tmp_path: Path) -> None:
    path = tmp_path / "t.tbl"
    path.write_text("01=a\n02=b\n2001=あ\n03=a\n; comment\n", encoding="utf-8")
    assert table_codes(path) == {"a": 1, "b": 2}


def test_a_glyph_moves_to_its_new_code() -> None:
    remapped = remap(_atlas(), {"a": 1, "b": 2}, {0x21: "a", 0x22: "c"})
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
    assert table_texts(path) == {1: "a", 2: "a"}
