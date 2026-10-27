import subprocess
import sys
from importlib.resources import files

import hatch_version
import pytest

import katsuji
from katsuji.atlas import Atlas


def test_ships_the_py_typed_marker() -> None:
    assert files("katsuji").joinpath("py.typed").is_file()


def test_script_loads_without_numpy_or_pillow() -> None:
    probe = "import sys, katsuji.script, katsuji.script.pointers; print(sorted({'numpy', 'PIL'} & set(sys.modules)))"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[]"


def test_top_level_names_load_on_first_use() -> None:
    assert katsuji.Atlas is Atlas


def test_unknown_name_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        _ = katsuji.nope


def test_dir_lists_the_public_names() -> None:
    assert "Atlas" in dir(katsuji)


def test_all_matches_the_lazy_table() -> None:
    assert sorted(katsuji.__all__) == sorted(katsuji._MODULES)


def test_render_stays_the_function_after_its_module_loads() -> None:
    probe = "import katsuji.render, katsuji; from katsuji import render; print(callable(render) and render.__module__)"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "katsuji.render"


@pytest.mark.parametrize(("tag", "version"), [("v0.5.0a2", "0.5.0a2"), ("0.5.0", "0.5.0"), ("", "0.0.0.dev0")])
def test_the_version_is_the_tag_without_its_v(monkeypatch: pytest.MonkeyPatch, tag: str, version: str) -> None:
    monkeypatch.setenv("VERSION", tag)
    assert hatch_version.get_version() == version
