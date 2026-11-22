"""`katsuji.script.sn`: snes.ninja script files read, and written in place."""

from pathlib import Path

import pytest

from katsuji.script import sn

DOCUMENT = """<?xml version="1.0" encoding="utf-8"?>
<sn:script xmlns:sn="http://snes.ninja/ScriptNS">
<!-- said: map $30 -->
<sn:pointer id="48:2" unused="1">Un &amp; deux
trois</sn:pointer>

<!-- said: map $31 -->
<sn:pointer id="48:10">Dix</sn:pointer>
</sn:script>
"""


@pytest.fixture
def script(tmp_path: Path) -> Path:
    path = tmp_path / "bank_048.xml"
    path.write_text(DOCUMENT, encoding="utf-8")
    return path


def test_a_pointer_reads_its_file_id_text_and_attributes(script: Path) -> None:
    assert sn.read(script)[0] == sn.Message("bank_048", "48:2", "Un & deux\ntrois", {"unused": "1"})


def test_pointers_read_in_file_order(script: Path) -> None:
    assert [message.id for message in sn.read(script)] == ["48:2", "48:10"]


def test_quotes_read_unescaped(tmp_path: Path) -> None:
    path = tmp_path / "a.xml"
    path.write_text('<sn:script><sn:pointer id="1">&quot;Oui&apos;</sn:pointer></sn:script>', encoding="utf-8")
    assert sn.read(path)[0].text == "\"Oui'"


def test_writing_changes_only_the_text(script: Path) -> None:
    sn.write(script, "48:10", "Onze <fin>")
    assert script.read_text(encoding="utf-8") == DOCUMENT.replace(">Dix<", ">Onze &lt;fin&gt;<")


def test_writing_keeps_the_attributes(script: Path) -> None:
    sn.write(script, "48:2", "Deux")
    assert sn.read(script)[0] == sn.Message("bank_048", "48:2", "Deux", {"unused": "1"})


def test_a_new_pointer_goes_before_the_next_id_and_its_comment(script: Path) -> None:
    sn.write(script, "48:5", "Cinq")
    text = script.read_text(encoding="utf-8")
    assert text.index('id="48:5"') < text.index("<!-- said: map $31 -->") < text.index('id="48:10"')


def test_a_new_pointer_keeps_the_files_spacing(script: Path) -> None:
    sn.write(script, "48:5", "Cinq")
    assert '<sn:pointer id="48:5">Cinq</sn:pointer>\n\n<!-- said: map $31 -->' in script.read_text(encoding="utf-8")


def test_a_last_pointer_goes_before_the_end(script: Path) -> None:
    sn.write(script, "48:99", "Fin")
    assert script.read_text(encoding="utf-8").endswith('<sn:pointer id="48:99">Fin</sn:pointer>\n\n</sn:script>\n')


def test_a_file_of_one_pointer_sets_pointers_a_line_apart() -> None:
    document = '<sn:script>\n<sn:pointer id="1">a</sn:pointer>\n</sn:script>'
    assert sn.replaced(document, "2", "b") == (
        '<sn:script>\n<sn:pointer id="1">a</sn:pointer>\n<sn:pointer id="2">b</sn:pointer>\n</sn:script>'
    )


def test_ids_sort_by_their_numbers() -> None:
    assert sorted(["45:100", "45:12", "menu:A", "45:2"], key=sn.natural) == ["45:2", "45:12", "45:100", "menu:A"]
