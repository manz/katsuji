"""`ScriptGame`: a game previewed from its `sn:script` dumps and its walker's `scenes.xml`."""

import re
from pathlib import Path

import numpy as np
import pytest

from katsuji.dialog import Window
from katsuji.flow import Judge, Laid
from katsuji.layout import TextLayout
from katsuji.png import Pixels
from katsuji.preview import Frame, Scene
from katsuji.preview.script_game import ScriptGame
from katsuji.script import sn
from katsuji.typeset import ENGLISH

HEAD = '<?xml version="1.0" encoding="utf-8"?>\n<sn:script xmlns:sn="http://snes.ninja/ScriptNS">\n'
SCENES = """<sn:scenes xmlns:sn="http://snes.ninja/ScriptNS">
  <sn:scene place="14:2" title="map $30">
    <sn:scene title="object 1 · talk"><sn:say ref="48:2"/><sn:say ref="48:1"/></sn:scene>
  </sn:scene>
  <sn:scene place="14:3" title="map $31"><sn:say ref="49:1"/></sn:scene>
  <sn:scene place="14:9" title="map $32"/>
  <sn:scene title="Menus"><sn:say ref="44:1"/></sn:scene>
</sn:scenes>
"""
LAYOUT = TextLayout(lambda line: len(line), 20, ENGLISH)


def files(root: Path, side: str, banks: dict[str, str]) -> Path:
    folder = root / side
    folder.mkdir()
    for name, pointers in banks.items():
        (folder / f"{name}.xml").write_text(HEAD + pointers + "</sn:script>\n", encoding="utf-8")
    return folder


@pytest.fixture
def game(tmp_path: Path) -> ScriptGame:
    fr = files(
        tmp_path,
        "fr",
        {
            "bank_014": '<sn:pointer id="14:2">Hikage</sn:pointer>\n<sn:pointer id="14:3">Hikage</sn:pointer>\n',
            "bank_044": '<sn:pointer id="44:1" frame="menu">Feu</sn:pointer>\n',
            "bank_048": '<sn:pointer id="48:1">Un.</sn:pointer>\n<sn:pointer id="48:2">Deux.</sn:pointer>\n'
            '<sn:pointer id="48:3" unused="1">Debug</sn:pointer>\n<sn:pointer id="48:4" shows="48:1"></sn:pointer>\n'
            '<sn:pointer id="48:5">Seul.</sn:pointer>\n',
        },
    )
    jp = files(
        tmp_path,
        "jp",
        {
            "bank_014": '<sn:pointer id="14:2">[kata]火影村</sn:pointer>\n<sn:pointer id="14:3">Hikage</sn:pointer>\n'
            '<sn:pointer id="14:9">裏山</sn:pointer>\n',
            "bank_049": '<sn:pointer id="49:1">エラー</sn:pointer>\n',
        },
    )
    (tmp_path / "scenes.xml").write_text(SCENES, encoding="utf-8")
    return ScriptGame(fr, frame_of, lay, jp, tmp_path / "scenes.xml", key="{id}")


def frame_of(message: sn.Message) -> Frame:
    return Frame(Judge(LAYOUT, Window(8 if message.attributes.get("frame") == "menu" else 20, 2)), 2, draw)


def draw(line: str, before: str) -> Pixels:
    return np.zeros((2, len(line)), dtype=np.uint8)


def lay(message: sn.Message, text: str) -> Laid:
    return [re.split(r"(?<=\.) ", text)]


def test_messages_are_keyed_by_the_template(game: ScriptGame) -> None:
    assert game.messages()[:3] == ["14:2", "14:3", "44:1"]


def test_the_default_key_names_the_file(tmp_path: Path, game: ScriptGame) -> None:
    plain = ScriptGame(game.translated, frame_of, lay)
    assert plain.messages()[0] == "bank_014:14:2"


def test_a_message_reads_its_text(game: ScriptGame) -> None:
    assert game.text("48:2") == "Deux."


def test_a_message_the_translation_lacks_reads_empty(game: ScriptGame) -> None:
    assert game.text("49:1") == ""


def test_the_original_is_the_other_sides(game: ScriptGame) -> None:
    assert game.original("14:2") == "[kata]火影村"


def test_without_originals_there_is_none(game: ScriptGame) -> None:
    assert ScriptGame(game.translated, frame_of, lay, key="{id}").original("14:2") is None


def test_a_scene_is_titled_by_its_place_translated_then_original(game: ScriptGame) -> None:
    assert game.scenes()[0].title == "Hikage · 火影村"


def test_a_place_named_alike_on_both_sides_is_named_once(game: ScriptGame) -> None:
    assert game.scenes()[1].title == "Hikage"


def test_an_untranslated_place_is_named_by_its_original(game: ScriptGame) -> None:
    assert game.scenes()[2].title == "裏山"


def test_a_place_title_loses_its_tags(game: ScriptGame) -> None:
    assert "[kata]" not in game.scenes()[0].title


def test_a_place_with_no_message_falls_back_to_its_title(game: ScriptGame) -> None:
    (game.scenes_file or Path()).write_text(
        SCENES.replace('place="14:9" title="map $32"', 'place="14:77" title="map $32"'), encoding="utf-8"
    )
    assert game.scenes()[2].title == "map $32"


def test_a_scene_without_place_keeps_its_title(game: ScriptGame) -> None:
    assert game.scenes()[3].title == "Menus"


def test_scenes_nest_and_keep_the_said_order(game: ScriptGame) -> None:
    assert game.scenes()[0].scenes[0] == Scene("object 1 · talk", ("48:2", "48:1"))


def test_what_no_scene_says_is_left_by_file(game: ScriptGame) -> None:
    assert game.scenes()[-1] == Scene(
        "Not in a scene", scenes=(Scene("bank_014", ("14:2", "14:3")), Scene("bank_048", ("48:5",)))
    )


def test_without_scenes_every_message_is_left(game: ScriptGame) -> None:
    alone = ScriptGame(game.translated, frame_of, lay, key="{id}")
    assert [scene.title for scene in alone.scenes()[0].scenes] == ["bank_014", "bank_044", "bank_048"]


def test_with_every_message_placed_nothing_is_left(tmp_path: Path) -> None:
    fr = files(tmp_path, "fr", {"a": '<sn:pointer id="1">Un.</sn:pointer>\n'})
    (tmp_path / "scenes.xml").write_text(
        '<sn:scenes xmlns:sn="http://snes.ninja/ScriptNS"><sn:scene title="A"><sn:say ref="1"/></sn:scene></sn:scenes>',
        encoding="utf-8",
    )
    assert [
        scene.title for scene in ScriptGame(fr, frame_of, lay, scenes_file=tmp_path / "scenes.xml", key="{id}").scenes()
    ] == ["A"]


def test_saving_writes_the_messages_file(game: ScriptGame) -> None:
    game.save("48:2", "Deux !")
    assert sn.read(game.translated / "bank_048.xml")[1].text == "Deux !"


def test_saving_is_read_back(game: ScriptGame) -> None:
    game.save("48:2", "Deux !")
    assert game.text("48:2") == "Deux !"


def test_saving_an_untranslated_message_adds_it_to_its_originals_file(game: ScriptGame) -> None:
    (game.translated / "bank_049.xml").write_text(HEAD + "</sn:script>\n", encoding="utf-8")
    game.save("49:1", "Erreur")
    assert sn.read(game.translated / "bank_049.xml")[0].text == "Erreur"


def test_an_unknown_message_is_an_error(game: ScriptGame) -> None:
    with pytest.raises(KeyError):
        game.message("99:9")


def test_the_frame_sees_the_messages_attributes(game: ScriptGame) -> None:
    assert game.frame("44:1").judge.window.width == 8


def test_the_layout_gets_the_message_and_text(game: ScriptGame) -> None:
    assert game.lay("48:1", "Un. Deux.") == [["Un.", "Deux."]]
