"""A game's dialog previewed and edited live: `katsuji preview module:game`, then a browser on it.

The game says what its messages are and how it lays them out and draws a line (`DialogGame`); katsuji serves a
page listing the messages (the worst flowing first, when sorted by cost), an editor whose every keystroke lays
the text out again, draws its windows (`katsuji.sheet`) and judges them (`katsuji.flow`), and saves the text back
through the game. Bound to the local machine only: it writes the game's files.

Needs the `preview` extra (starlette, uvicorn).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from katsuji.flow import Flaws, Judge, Laid
from katsuji.png import Pixels, encode
from katsuji.sheet import PALETTE, window_sheet


class DialogGame(Protocol):
    """What a game gives the preview. Its `judge` holds the layout and window its dialog is laid out to."""

    @property
    def judge(self) -> Judge: ...

    @property
    def line_height(self) -> int: ...

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
        """`text` laid out by the game's rules into windows, each its lines, as `judge` reads them."""
        ...

    def draw(self, line: str, before: str) -> Pixels:
        """A line drawn as the game draws it (0 paper, else ink), `before` the lines drawn ahead of it in the
        message (a font switch holding across lines)."""
        ...


@dataclass(frozen=True)
class View:
    """A text laid out: its windows drawn as a PNG, what breaks them, what reads badly, and what that costs."""

    png: bytes
    faults: list[str]
    flaws: Flaws
    cost: int


@dataclass
class Preview:
    """The game's messages laid out, drawn and judged; each message's saved cost kept once worked out."""

    game: DialogGame
    costs: dict[str, int] = field(default_factory=dict)

    def listing(self, query: str = "", by_cost: bool = False) -> list[tuple[str, int | None]]:
        """The messages whose key or text holds `query`, each with its saved cost when known (all of them, worked
        out now, when `by_cost`: the costliest first)."""
        found = [key for key in self.game.messages() if self._matches(key, query)]
        if by_cost:
            return sorted(((key, self.cost(key)) for key in found), key=lambda item: -(item[1] or 0))
        return [(key, self.costs.get(key)) for key in found]

    def cost(self, key: str) -> int:
        """The message's cost as saved."""
        if key not in self.costs:
            self.costs[key] = self.game.judge.cost(self.game.lay(key, self.game.text(key)))
        return self.costs[key]

    def view(self, key: str, text: str) -> View:
        laid = self.game.lay(key, text)
        judge = self.game.judge
        flaws = judge.flaws(laid)
        return View(self._png(laid), judge.faults(laid), flaws, flaws.cost(judge.weights))

    def save(self, key: str, text: str) -> View:
        self.game.save(key, text)
        view = self.view(key, text)
        self.costs[key] = view.cost
        return view

    def _png(self, laid: Laid) -> bytes:
        drawn: list[list[Pixels]] = []
        before = ""
        for lines in laid:
            drawn.append([])
            for line in lines:
                drawn[-1].append(self.game.draw(line, before))
                before = f"{before}\n{line}" if before else line
        return encode(window_sheet(drawn, self.game.judge.window, self.game.line_height), palette=PALETTE)

    def _matches(self, key: str, query: str) -> bool:
        return not query or query in key or query.casefold() in self.game.text(key).casefold()
