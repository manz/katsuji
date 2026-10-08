from __future__ import annotations

from importlib.resources import files


def test_ships_the_py_typed_marker() -> None:
    assert files("katsuji").joinpath("py.typed").is_file()
