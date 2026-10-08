"""`katsuji.toml` + `katsuji build`: ff4's fonts described in config rebuild byte for byte."""

import json
from pathlib import Path

import pytest

from katsuji.build import build
from katsuji.cli import main
from katsuji.config import ConfigError, load
from katsuji.formats import VwfFont
from tests.test_ff4_fonts import _DIALOG_CANDIDATES, _MENU_CANDIDATES

FF4 = Path(__file__).parent / "fixtures" / "ff4"


def _toml(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _ff4_config(tmp_path: Path) -> Path:
    dialog = "\n".join(
        f"""
[fonts.{name}]
png = "{FF4 / png}"
table = "{FF4 / "ff4fr.tbl"}"
output = "out/{name}.dat"
widths = {{ "0xFF" = {space}, "0xFD" = 1, "0xFE" = 2, "0xA0" = -1 }}
kerning-candidates = {_toml(list(_DIALOG_CANDIDATES))}
kerning = {{ "tt" = 2 }}
"""
        for name, png, space in [("font", "vwf.png", 3), ("bold", "bold_vwf.png", 5), ("book", "book_vwf.png", 5)]
    )
    menu = f"""
[fonts.menu]
png = "{FF4 / "8x8vwf.png"}"
cell = [8, 8]
table = "{FF4 / "ff4_menus.tbl"}"
output = "out/menu.dat"
widths = {{ "0xFF" = 3 }}
kerning-candidates = {_toml(_MENU_CANDIDATES)}
constants = "out/menu.i"

[strings.items]
font = "menu"
texts = ["Potion", "Ether"]
blob = "out/items.dat"
index = "out/items.idx"
constants = "out/items.i"
"""
    path = tmp_path / "katsuji.toml"
    path.write_text(dialog + menu, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def ff4_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = _ff4_config(tmp_path_factory.mktemp("ff4"))
    build(load(path))
    return path.parent / "out"


@pytest.mark.parametrize(
    ("built", "golden"),
    [
        ("font.dat", "font.dat"),
        ("bold.dat", "bold_font.dat"),
        ("book.dat", "book_font.dat"),
        ("menu.dat", "menu_font.dat"),
    ],
)
def test_ff4_fonts_build_from_config(ff4_build: Path, built: str, golden: str) -> None:
    assert (ff4_build / built).read_bytes() == (FF4 / golden).read_bytes()


def test_font_constants_describe_the_file(ff4_build: Path) -> None:
    assert "MENU_FONT_GLYPH_SIZE = 9" in (ff4_build / "menu.i").read_text()


def test_strings_index_one_entry_per_text(ff4_build: Path) -> None:
    assert len((ff4_build / "items.idx").read_bytes()) == 2 * 4


def test_strings_blob_holds_the_indexed_tiles(ff4_build: Path) -> None:
    index = (ff4_build / "items.idx").read_bytes()
    last_offset, last_tiles = index[4] | index[5] << 8, index[7]
    assert len((ff4_build / "items.dat").read_bytes()) == last_offset + last_tiles * 16


def test_strings_constants_count_the_texts(ff4_build: Path) -> None:
    assert "ITEMS_COUNT = 2" in (ff4_build / "items.i").read_text()


@pytest.mark.parametrize("constants", ["menu.i", "items.i"])
def test_constants_parse_as_a816(ff4_build: Path, constants: str) -> None:
    from a816.parse.mzparser import A816Parser

    result = A816Parser.parse_as_ast((ff4_build / constants).read_text(), filename=constants)
    assert result.parse_error is None


def _config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "katsuji.toml"
    path.write_text(text, encoding="utf-8")
    return path


_PNG = f'png = "{FF4 / "vwf.png"}"\noutput = "f.dat"\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[colors]\n", "unknown table"),
        (f"[fonts.f]\n{_PNG}size = 3\n", r"\[fonts.f\] unknown key\(s\) \['size'\]"),
        ("[fonts.f]\noutput = 'f.dat'\n", r"missing key\(s\) \['png'\]"),
        (f"[fonts.f]\n{_PNG}widths = {{ 'space' = 3 }}\n", "is not a code"),
        ("[strings.s]\nfont = 'f'\nblob = 'b'\nindex = 'i'\ntexts = ['a']\n", "is not a \\[fonts.NAME\\]"),
        ("[strings.s]\nfont = 'f'\nblob = 'b'\nindex = 'i'\n", "exactly one of `texts` and `file`"),
        ("[fonts.f\n", "katsuji.toml"),
    ],
)
def test_config_errors_name_the_table_and_key(tmp_path: Path, text: str, message: str) -> None:
    path = _config(tmp_path, text)
    with pytest.raises(ConfigError, match=message):
        load(path)


def test_strings_can_read_their_texts_from_a_file(tmp_path: Path) -> None:
    (tmp_path / "items.txt").write_text("Potion\n\nEther\n")
    path = _config(
        tmp_path,
        f"[fonts.f]\n{_PNG}[strings.s]\nfont = 'f'\nblob = 'b'\nindex = 'i'\nfile = 'items.txt'\n",
    )
    assert load(path).strings["s"].texts == ("Potion", "Ether")


def test_a_kerning_pair_must_be_two_codes(tmp_path: Path) -> None:
    config = load(_config(tmp_path, f"[fonts.f]\n{_PNG}table = '{FF4 / 'ff4fr.tbl'}'\nkerning = {{ 'abc' = 1 }}\n"))
    with pytest.raises(ConfigError, match="encodes to 3 codes"):
        build(config)


def test_kerning_needs_a_table(tmp_path: Path) -> None:
    config = load(_config(tmp_path, f"[fonts.f]\n{_PNG}kerning = {{ 'ab' = 1 }}\n"))
    with pytest.raises(ConfigError, match="needs a `table`"):
        build(config)


def test_a_font_without_kerning_needs_no_table(tmp_path: Path) -> None:
    build(load(_config(tmp_path, f"[fonts.f]\n{_PNG}")))
    assert VwfFont.decode((tmp_path / "f.dat").read_bytes()).kerning == {}


def test_cli_build_lists_what_it_wrote(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["build", str(_config(tmp_path, f"[fonts.f]\n{_PNG}"))])
    assert capsys.readouterr().out.strip().endswith("f.dat")


def test_cli_build_reports_config_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["build", str(_config(tmp_path, "[colors]\n"))])
    assert (code, "unknown table" in capsys.readouterr().err) == (2, True)
