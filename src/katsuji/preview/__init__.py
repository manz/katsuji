"""A game's dialog previewed and edited live: `katsuji preview module:game`, then a browser on it.

The game says what its messages are, how each is laid out and drawn (`DialogGame`), and, when it knows, where each
is said (`Scene`s: a map, an object talked to, the messages in the order the script says them). katsuji serves a
page listing the messages by scene, or found by text, or the worst flowing first; an editor whose every keystroke
lays the text out again, draws its windows (`katsuji.sheet`) and judges them (`katsuji.flow`); and saves the text
back through the game. Bound to the local machine only: it writes the game's files.

Needs the `preview` extra (starlette, uvicorn).
"""

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from katsuji.flow import Flaws, Judge, Laid
from katsuji.png import Pixels, encode
from katsuji.sheet import PALETTE, window_sheet

SNIPPET = 40  # characters of a message shown in a listing


@dataclass(frozen=True)
class Frame:
    """How a message is set and drawn: its `judge` (the layout and window it is laid out to), its lines'
    height, and `draw`, a line drawn as the game draws it (0 paper, else ink) given the lines drawn ahead of it in
    the message (a font switch holding across lines). Dialog and menus differ: their fonts, their windows."""

    judge: Judge
    line_height: int
    draw: Callable[[str, str], Pixels]


@dataclass(frozen=True)
class Scene:
    """Where messages are said: a `title`, its own messages' keys in the order they are said, and the scenes
    inside it."""

    title: str
    keys: Sequence[str] = ()
    scenes: Sequence[Scene] = ()

    def all_keys(self) -> Iterator[str]:
        yield from self.keys
        for scene in self.scenes:
            yield from scene.all_keys()


class DialogGame(Protocol):
    """What a game gives the preview."""

    def messages(self) -> Sequence[str]:
        """Every message's key ("102:2"), in the order to list them."""
        ...

    def text(self, key: str) -> str:
        """The message as the script keeps it, to edit."""
        ...

    def original(self, key: str) -> str | None:
        """The text translated from (the Japanese), shown beside the editor; None: none."""
        ...

    def save(self, key: str, text: str) -> None:
        """Write `text` back to the script as the message's."""
        ...

    def lay(self, key: str, text: str) -> Laid:
        """`text` laid out by the game's rules into windows, each its lines, as its frame's judge reads them."""
        ...

    def frame(self, key: str) -> Frame:
        """How the message is set and drawn."""
        ...


@runtime_checkable
class Staged(Protocol):
    """A game that knows where its messages are said."""

    def scenes(self) -> Sequence[Scene]: ...


@dataclass(frozen=True)
class View:
    """A text laid out: its windows drawn as a PNG, what breaks them, what reads badly, and what that costs."""

    png: bytes
    faults: list[str]
    flaws: Flaws
    cost: int


@dataclass(frozen=True)
class Row:
    """A message in a listing: what it says (its original's words when it has no text yet: `untranslated`), and
    how its saved text reads when worked out."""

    key: str
    snippet: str
    cost: int | None = None
    faults: int = 0
    flaws: Flaws = field(default_factory=Flaws)
    untranslated: bool = False


@dataclass
class Preview:
    """The game's messages laid out, drawn and judged; each message's saved flow kept once worked out."""

    game: DialogGame
    judged: dict[str, tuple[Flaws, int, int]] = field(default_factory=dict)
    """Per message: its flaws, its faults, its cost."""
    staged: list[Scene] | None = None

    def scenes(self) -> list[Scene]:
        """The game's scenes, asked once, or one scene of every message when it knows none."""
        if self.staged is None:
            found = self.game.scenes() if isinstance(self.game, Staged) else [Scene("Messages", self.game.messages())]
            self.staged = list(found)
        return self.staged

    def scene(self, path: str) -> Scene:
        """The scene at `path`, indices from the top down ("0/3")."""
        scenes: Sequence[Scene] = self.scenes()
        found = Scene("")
        for index in path.split("/"):
            found = scenes[int(index)]
            scenes = found.scenes
        return found

    def rows(self, keys: Sequence[str], judge: bool = False) -> list[Row]:
        """The messages of `keys` as listed, judged now when `judge`, else as far as known."""
        if judge:
            for key in keys:
                self.cost(key)
        return [self.row(key) for key in keys]

    def row(self, key: str) -> Row:
        text = self.game.text(key)
        untranslated = not text.strip()
        snippet = self._snippet(key, (self.game.original(key) or "") if untranslated else text)
        if key not in self.judged:
            return Row(key, snippet, untranslated=untranslated)
        flaws, faults, cost = self.judged[key]
        return Row(key, snippet, cost, faults, flaws, untranslated)

    def total(self, scene: Scene) -> Row:
        """A scene's messages summed up, judged now."""
        keys = list(dict.fromkeys(scene.all_keys()))
        rows = self.rows(keys, judge=True)
        flaws = sum((row.flaws for row in rows), Flaws())
        return Row(scene.title, f"{len(keys)}", sum(row.cost or 0 for row in rows), sum(r.faults for r in rows), flaws)

    def found(self, query: str = "", by_cost: bool = False) -> list[Row]:
        """The messages whose key or text holds `query`; when `by_cost`, all of them judged, the costliest first."""
        keys = [key for key in self.game.messages() if self._matches(key, query)]
        rows = self.rows(keys, judge=by_cost)
        return sorted(rows, key=lambda row: -(row.cost or 0)) if by_cost else rows

    def cost(self, key: str) -> int:
        """The message's cost as saved."""
        if key not in self.judged:
            view = self.view(key, self.game.text(key), draw=False)
            self.judged[key] = (view.flaws, len(view.faults), view.cost)
        return self.judged[key][2]

    def view(self, key: str, text: str, draw: bool = True) -> View:
        frame = self.game.frame(key)
        laid = self.game.lay(key, text)
        flaws = frame.judge.flaws(laid)
        png = self._png(frame, laid) if draw else b""
        return View(png, frame.judge.faults(laid), flaws, flaws.cost(frame.judge.weights))

    def save(self, key: str, text: str) -> View:
        self.game.save(key, text)
        view = self.view(key, text)
        self.judged[key] = (view.flaws, len(view.faults), view.cost)
        return view

    def _png(self, frame: Frame, laid: Laid) -> bytes:
        drawn: list[list[Pixels]] = []
        before = ""
        for lines in laid:
            drawn.append([])
            for line in lines:
                drawn[-1].append(frame.draw(line, before))
                before = f"{before}\n{line}" if before else line
        return encode(window_sheet(drawn, frame.judge.window, frame.line_height), palette=PALETTE)

    def _snippet(self, key: str, text: str) -> str:
        tag = self.game.frame(key).judge.layout.markup.tag
        plain = " ".join(re.sub(tag, " ", text, flags=re.IGNORECASE).split())
        return plain if len(plain) <= SNIPPET else plain[: SNIPPET - 1] + "…"

    def _matches(self, key: str, query: str) -> bool:
        return not query or query in key or query.casefold() in self.game.text(key).casefold()
