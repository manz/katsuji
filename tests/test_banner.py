from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from katsuji import VwfFont
from katsuji.banner import banner, runs, to_blocks
from katsuji.cli import main
from katsuji.wrap import Controls, Fixed

FF4 = Path(__file__).parent / "fixtures" / "ff4"
SWITCH = 0xFE
A, B = 1, 2


def _font(ink: int = 0x80, width: int = 1) -> VwfFont:
    glyphs = [bytes([ink])] * 256
    return VwfFont(1, glyphs, [width] * 256)


def test_runs_split_at_font_switches() -> None:
    controls = Controls(font_switch=SWITCH)
    assert runs(bytes([A, SWITCH, 1, B]), controls) == [(0, [A]), (1, [B])]


def test_runs_skip_fixed_codes_and_their_arguments() -> None:
    controls = Controls(fixed={0x04: Fixed(1, 48)})
    assert runs(bytes([A, 0x04, 9, B]), controls) == [(0, [A, B])]


def test_each_run_is_set_with_its_font() -> None:
    fonts = [_font(), _font(ink=0xC0, width=2)]
    pixels = banner(fonts, bytes([A, SWITCH, 1, A]), Controls(font_switch=SWITCH))
    assert pixels.tolist() == [[1, 1, 1]]


def test_kerning_can_be_turned_off() -> None:
    font = _font()
    font.kerning = {(A, B): 1}
    pixels = banner([font], bytes([A, B]), Controls(), kerning=False)
    assert pixels.shape[1] == 3


def test_nothing_to_draw_is_an_empty_banner() -> None:
    assert banner([_font()], b"", Controls()).shape == (0, 0)


def test_blocks_are_two_characters_per_pixel() -> None:
    assert to_blocks(np.array([[1, 0]], dtype=np.uint8)) == "██  "


def test_cli_prints_the_banner(capsys: pytest.CaptureFixture[str]) -> None:
    main(["banner", "Ta", "--table", str(FF4 / "ff4fr.tbl"), "--font", str(FF4 / "font.dat")])
    assert "██" in capsys.readouterr().out


def test_cli_saves_a_png(tmp_path: Path) -> None:
    out = tmp_path / "banner.png"
    main(["banner", "Ta", "--table", str(FF4 / "ff4fr.tbl"), "--font", str(FF4 / "font.dat"), "--png", str(out)])
    assert Image.open(out).size[1] == 16


def test_cli_switches_fonts_on_the_switch_code(capsys: pytest.CaptureFixture[str]) -> None:
    fonts = [str(FF4 / name) for name in ("font.dat", "wicked_font.dat")]
    args = ["banner", "a[wicked]a", "--table", str(FF4 / "ff4fr.tbl"), "--font-switch", "0xFE"]
    main([*args, "--font", fonts[0], "--font", fonts[1]])
    assert "██" in capsys.readouterr().out
