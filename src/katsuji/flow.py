"""How well dialog flows over windows: what a reader feels at each button press, counted.

`windows` pours text in; whether what comes out reads well is a separate question, answered here for any
game's laid-out windows (each window as its lines):

- `Judge.faults`: what breaks a window outright (a line wider than its row, more lines than the window holds,
  an empty window). Any is a bug.
- `Judge.flaws`: what reads badly, counted by kind (`Flaws`). `Flaws.cost` weighs them into one number, lower
  reading better: two flows of the same text compare by it.
- `Report`: flaws over a whole script, keyed by message: totals, the worst messages, and what changed since a
  report saved earlier (`Report.dump`, `load`).

Lines are measured through the `TextLayout` that laid them out, `measure_after` seeing every line ahead; tags
are its `markup`'s. far_fast_of_eden_zero's tools/reflow.py (`cost`, `dangling`) is where this comes from.
"""

import itertools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields

from katsuji.dialog import Window
from katsuji.layout import TextLayout

Laid = Sequence[Sequence[str]]
"""Windows, each its lines: what `katsuji.windows.windows` returns."""

SENTENCE_END = r"[.!?…][\"'»”)\s]*$"


@dataclass(frozen=True)
class Flaws:
    """What reads badly in a flow, counted."""

    windows: int = 0
    """Windows: each one more button press."""
    carried: int = 0
    """Windows turned in the middle of a sentence: the reader presses on mid-thought."""
    dangles: int = 0
    """Of those, the turns that carry only the last few words of the sentence: a window opened for nearly
    nothing."""
    lone: int = 0
    """Windows of one line that another follows."""
    empty: int = 0
    """Lines left empty in windows that another follows: room the text did not need to turn for."""
    tails: int = 0
    """Sentences broken over lines whose last line is short: a ragged block."""

    def __add__(self, other: Flaws) -> Flaws:
        return Flaws(**{name: getattr(self, name) + getattr(other, name) for name in _names()})

    def cost(self, weights: Weights | None = None) -> int:
        """The flaws weighed into one number: lower reads better."""
        weights = weights or Weights()
        return sum(getattr(self, name) * getattr(weights, name) for name in _names())


@dataclass(frozen=True)
class Weights:
    """What each flaw of `Flaws` costs. A window costs most: a layout is first as short as it can be, then as
    clean."""

    windows: int = 10
    carried: int = 4
    dangles: int = 5
    lone: int = 3
    empty: int = 1
    tails: int = 2


def _names() -> list[str]:
    return [item.name for item in fields(Flaws)]


@dataclass(frozen=True)
class Judge:
    """Reads windows laid out by `layout` into `window`'s size.

    `sentence_end` matches the end of a line that ends a sentence, its tags taken out; `dangle_words` is how
    few words a turn may carry to count as a dangle (a pause, "......", has none and never does); a sentence's
    last line narrower than `tail` of its row is a tail."""

    layout: TextLayout
    window: Window
    sentence_end: str = SENTENCE_END
    dangle_words: int = 2
    tail: float = 0.25
    weights: Weights = field(default_factory=Weights)

    def faults(self, laid: Laid) -> list[str]:
        """What breaks a window: an empty one, one of too many lines, a line wider than its row."""
        found = []
        for number, lines in enumerate(laid, 1):
            if not lines:
                found.append(f"window {number}: empty")
            if len(lines) > self.window.lines:
                found.append(f"window {number}: {len(lines)} lines, holds {self.window.lines}")
            found.extend(
                f"window {number}: {line!r} {width} px, row {row} holds {self.window.line_width(row)}"
                for row, line, width in self._widths(laid, number - 1)
                if width > self.window.line_width(row)
            )
        return found

    def flaws(self, laid: Laid) -> Flaws:
        turns = [(before[-1], after[0]) for before, after in itertools.pairwise(laid) if before and after]
        carried = [first for last, first in turns if not self.ends(last)]
        return Flaws(
            windows=len(laid),
            carried=len(carried),
            dangles=sum(self._dangles(first) for first in carried),
            lone=sum(len(lines) == 1 for lines in laid[:-1]),
            empty=sum(max(self.window.lines - len(lines), 0) for lines in laid[:-1]),
            tails=sum(self._tails(laid, index) for index in range(len(laid))),
        )

    def cost(self, laid: Laid) -> int:
        return self.flaws(laid).cost(self.weights)

    def ends(self, line: str) -> bool:
        """`line` ends a sentence."""
        return bool(re.search(self.sentence_end, self._plain(line)))

    def _dangles(self, first: str) -> bool:
        """`first`, opening a window mid-sentence, ends the sentence in `dangle_words` words or fewer."""
        plain = self._plain(first)
        words = plain.split()
        return self.ends(first) and any(char.isalpha() for char in plain) and len(words) <= self.dangle_words

    def _tails(self, laid: Laid, index: int) -> int:
        """Lines of window `index` ending a sentence that broke onto them from the line above, narrower than
        `tail` of their row."""
        lines = laid[index]
        widths = {row: width for row, _, width in self._widths(laid, index)}
        return sum(
            self.ends(line) and not self.ends(above) and widths[row] < self.tail * self.window.line_width(row)
            for row, (above, line) in enumerate(itertools.pairwise(lines), 1)
        )

    def _widths(self, laid: Laid, index: int) -> list[tuple[int, str, int]]:
        """Window `index`'s lines, each with its row and width, measured after every line laid out ahead."""
        before = "\n".join(line for lines in laid[:index] for line in lines)
        measured = []
        for row, line in enumerate(laid[index]):
            measured.append((row, line, self.layout.measure_line(line, before)))
            before = f"{before}\n{line}" if before else line
        return measured

    def _plain(self, line: str) -> str:
        return re.sub(self.layout.markup.tag, "", line, flags=re.IGNORECASE)


@dataclass
class Report:
    """Flows over a whole script, keyed by message, judged by `judge`."""

    judge: Judge
    flaws: dict[str, Flaws] = field(default_factory=dict)
    faults: dict[str, list[str]] = field(default_factory=dict)

    def add(self, key: str, laid: Laid) -> None:
        self.flaws[key] = self.judge.flaws(laid)
        if faults := self.judge.faults(laid):
            self.faults[key] = faults

    def totals(self) -> Flaws:
        return sum(self.flaws.values(), Flaws())

    def worst(self, count: int = 20) -> list[tuple[str, int]]:
        """The `count` messages that cost most past their windows, the costliest first: windows alone are what the
        text takes, not how it flows."""
        weights = self.judge.weights
        costs = [(key, flaws.cost(weights) - flaws.windows * weights.windows) for key, flaws in self.flaws.items()]
        return sorted((item for item in costs if item[1]), key=lambda item: -item[1])[:count]

    def dump(self) -> str:
        """The flaws as JSON, to `load` and compare against after a change."""
        return json.dumps({key: asdict(flaws) for key, flaws in self.flaws.items()}, indent=1, sort_keys=True)

    def changes(self, before: Mapping[str, Flaws]) -> list[str]:
        """What moved since `before`: each kind of flaw's total, then each message whose cost did, the most
        changed first."""
        then = sum(before.values(), Flaws())
        now = self.totals()
        lines = [
            f"{name}: {getattr(then, name)} → {getattr(now, name)}"
            for name in _names()
            if getattr(then, name) != getattr(now, name)
        ]
        return lines + self._moved(before)

    def _moved(self, before: Mapping[str, Flaws]) -> list[str]:
        weights = self.judge.weights
        moved = []
        for key in sorted(before.keys() | self.flaws.keys()):
            then = before[key].cost(weights) if key in before else None
            now = self.flaws[key].cost(weights) if key in self.flaws else None
            if then != now:
                moved.append((abs((now or 0) - (then or 0)), f"{key}: {_or_gone(then)} → {_or_gone(now)}"))
        return [line for _, line in sorted(moved, key=lambda item: -item[0])]


def load(text: str) -> dict[str, Flaws]:
    """A `Report.dump` read back."""
    return {key: Flaws(**counts) for key, counts in json.loads(text).items()}


def _or_gone(cost: int | None) -> str:
    return "gone" if cost is None else str(cost)
