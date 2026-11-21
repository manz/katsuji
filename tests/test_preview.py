"""`katsuji preview`: a game's dialog laid out, drawn, judged and saved, over HTTP. A monospace font draws one
column of ink per character."""

import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest
from starlette.testclient import TestClient

from katsuji import cli
from katsuji.dialog import Window
from katsuji.flow import Judge, Laid
from katsuji.layout import TextLayout
from katsuji.png import Pixels, decode
from katsuji.preview import Preview, app
from katsuji.typeset import ENGLISH
from katsuji.windows import Paragraph, windows


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line))


LAYOUT = TextLayout(monospace, 12, ENGLISH)


@dataclass
class Game:
    texts: dict[str, str] = field(
        default_factory=lambda: {"1:1": "Hello. How are you?", "1:2": "One two three four five six seven eight."}
    )
    judge: Judge = field(default_factory=lambda: Judge(LAYOUT, Window(12, 2)))
    line_height: int = 2
    befores: list[str] = field(default_factory=list)

    def messages(self) -> list[str]:
        return list(self.texts)

    def text(self, key: str) -> str:
        return self.texts[key]

    def original(self, key: str) -> str | None:
        return "こんにちは" if key == "1:1" else None

    def save(self, key: str, text: str) -> None:
        self.texts[key] = text

    def lay(self, key: str, text: str) -> Laid:
        return windows(LAYOUT, [Paragraph(re.split(r"(?<=[.?]) ", text))], self.judge.window)

    def draw(self, line: str, before: str) -> Pixels:
        self.befores.append(before)
        return np.ones((2, monospace(line)), dtype=np.uint8)


def client(game: Game | None = None) -> TestClient:
    return TestClient(app.app(game or Game()))


def test_a_message_costs_what_its_saved_text_does() -> None:
    assert Preview(Game()).cost("1:1") == 10


def test_the_listing_holds_every_message_in_order() -> None:
    assert Preview(Game()).listing() == [("1:1", None), ("1:2", None)]


def test_the_listing_filters_by_key() -> None:
    assert [key for key, _ in Preview(Game()).listing("1:2")] == ["1:2"]


def test_the_listing_filters_by_text_whatever_the_case() -> None:
    assert [key for key, _ in Preview(Game()).listing("HELLO")] == ["1:1"]


def test_by_cost_the_costliest_comes_first() -> None:
    assert [key for key, _ in Preview(Game()).listing(by_cost=True)] == ["1:2", "1:1"]


def test_a_cost_worked_out_shows_in_the_listing() -> None:
    preview = Preview(Game())
    preview.cost("1:1")
    assert preview.listing() == [("1:1", 10), ("1:2", None)]


def test_a_view_draws_the_windows() -> None:
    pixels, _ = decode(Preview(Game()).view("1:2", "One two three four five six seven eight.").png)
    assert pixels.shape[0] > 2 * (2 * 2)


def test_each_line_is_drawn_after_the_lines_ahead() -> None:
    game = Game()
    Preview(game).view("1:1", "Hello. How are you?")
    assert game.befores == ["", "Hello."]


def test_a_view_judges_the_text() -> None:
    assert Preview(Game()).view("1:1", "Hello. How are you?").flaws.windows == 1


def test_a_view_finds_the_faults() -> None:
    assert Preview(Game()).view("1:1", "Supercalifragilistic.").faults != []


def test_saving_writes_through_the_game_and_keeps_the_cost() -> None:
    game = Game()
    preview = Preview(game)
    preview.save("1:1", "Hi.")
    assert (game.texts["1:1"], preview.costs["1:1"]) == ("Hi.", 10)


def test_the_page_lists_the_messages() -> None:
    body = client().get("/").text
    assert ("htmx.min.js" in body, "1:1" in body, "1:2" in body) == (True, True, True)


def test_htmx_is_served() -> None:
    assert client().get("/static/htmx.min.js").text.startswith("var htmx")


def test_the_messages_fragment_filters() -> None:
    assert "1:1" not in client().get("/messages", params={"q": "eight"}).text


def test_the_messages_fragment_sorts_by_cost() -> None:
    body = client().get("/messages", params={"sort": "cost"}).text
    assert body.index("1:2") < body.index("1:1")


def test_a_message_opens_in_the_editor_with_its_original() -> None:
    body = client().get("/message", params={"key": "1:1"}).text
    assert ("Hello. How are you?</textarea>" in body, "こんにちは" in body) == (True, True)


def test_a_message_without_original_shows_none() -> None:
    assert 'class="original"' not in client().get("/message", params={"key": "1:2"}).text


def test_the_editor_escapes_the_text() -> None:
    game = Game(texts={"1:1": "<b>Hi.</b>"})
    assert "&lt;b&gt;Hi.&lt;/b&gt;" in client(game).get("/message", params={"key": "1:1"}).text


def test_a_preview_shows_the_windows_and_the_cost_against_the_saved() -> None:
    body = client().post("/preview", data={"key": "1:1", "text": "One two three four five six seven eight."}).text
    assert ("data:image/png;base64," in body, 'class="worse"' in body) == (True, True)


def test_a_shorter_text_reads_better() -> None:
    body = client().post("/preview", data={"key": "1:2", "text": "Hi."}).text
    assert 'class="better"' in body


def test_a_preview_shows_its_faults() -> None:
    assert 'class="fault"' in client().post("/preview", data={"key": "1:1", "text": "Supercalifragilistic."}).text


def test_saving_writes_and_says_so() -> None:
    game = Game()
    body = client(game).post("/save", data={"key": "1:1", "text": "Hi."}).text
    assert (game.texts["1:1"], "saved" in body) == ("Hi.", True)


GAME_MODULE = """
from tests.test_preview import Game
game = Game()
def make():
    return Game(texts={"9:9": "Made."})
"""


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    (tmp_path / "some_game.py").write_text(GAME_MODULE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).parent.parent))
    yield "some_game"
    sys.modules.pop("some_game", None)


def test_a_game_loads_from_module_and_attribute(module: str) -> None:
    assert app.load(f"{module}:game").messages() == ["1:1", "1:2"]


def test_a_game_loads_from_a_function(module: str) -> None:
    assert app.load(f"{module}:make").messages() == ["9:9"]


def test_a_game_needs_its_attribute() -> None:
    with pytest.raises(ValueError, match="module:attribute"):
        app.load("some_game")


def test_serving_binds_the_local_machine(module: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr("uvicorn.run", lambda _app, host, port: calls.append((host, port)))
    assert cli.main(["preview", f"{module}:game", "--port", "9000"]) == 0
    assert calls == [("127.0.0.1", 9000)]
