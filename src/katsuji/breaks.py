"""A sentence broken over a set number of lines where its phrases part, not where the lines come out narrowest.

Dynamic programming over the word positions, as Knuth and Plass break a paragraph, on a cost per line:

- a line's slack, squared, so the lines stay full and even;
- ending on a word that leans on the next (an article, a preposition, a pronoun: `PhraseBreaks.binding`) costs
  much, on an auxiliary less;
- ending after a comma, a semicolon or an ellipsis, or before a word opening a clause or a phrase, earns;
- the last line costs when it is short, more when it is a single word.

The weights were tuned on ff4's French script; a game checks its own before opting in.
"""

from collections.abc import Callable, Sequence

from katsuji.typeset import PhraseBreaks

_FULL = 100.0
"""A line's cost per squared fraction of the width left empty."""
_BINDING = 60.0
_AUXILIARY = 0.6
"""Of `_BINDING`."""
_CLAUSE = 25.0
"""Earned ending after a comma, a semicolon or an ellipsis."""
_OPENER = 0.8
"""Of `_CLAUSE`, before a clause opener."""
_PREPOSITION = 0.4
"""Of `_CLAUSE`, before a preposition."""
_SHORT_LAST = 0.4
"""Of the width: a last line narrower costs."""
_SHORT_LAST_COST = 400.0
_WIDOW = 80.0
"""A last line of one word."""
_SPARE = 25.0
"""A line more than asked for: taken only when it breaks clearly better."""
_CLOSING = "»” "
_OPENING = "«“ "
_APOSTROPHE = str.maketrans({"\u2019": "'"})
"""A typographic apostrophe matched as the straight one."""


def break_by_cost(
    words: Sequence[str],
    lines: int,
    width: Callable[[int, int], int],
    limit: int,
    breaks: PhraseBreaks,
    first_words: int = 1,
    spare: int = 0,
) -> list[int] | None:
    """Where `words` end each of `lines` lines, the cheapest way: the index after each line's last word. `words`
    are plain (tags off), `width(i, j)` measures `words[i:j]` set as a line, `limit` is the widest a line may be,
    and the first line takes at least `first_words` (2 keeps a speaker label off a line of its own). Up to
    `spare` lines more are taken when they break clearly better. None when no break gives `lines` lines that fit."""
    count = len(words)
    most = lines + spare
    best: list[list[float | None]] = [[None] * (most + 1) for _ in range(count + 1)]
    back: dict[tuple[int, int], int] = {}
    best[0][0] = 0.0
    for end in range(1, count + 1):
        for line in range(1, most + 1):
            for start in range(end - 1, -1, -1):
                ahead = best[start][line - 1]
                if ahead is None:
                    continue
                used = width(start, end)
                if used > limit:
                    break
                if start == 0 and end < min(first_words, count):
                    continue
                cost = ahead + _line_cost(words, start, end, used, limit, breaks)
                current = best[end][line]
                if current is None or cost < current:
                    best[end][line] = cost
                    back[(end, line)] = start
    if best[count][lines] is None:
        return None
    taken = min(
        (total + (taken - lines) * _SPARE, taken)
        for taken in range(lines, most + 1)
        if (total := best[count][taken]) is not None
    )[1]
    ends, end = [], count
    for line in range(taken, 0, -1):
        ends.append(end)
        end = back[(end, line)]
    return ends[::-1]


def _line_cost(words: Sequence[str], start: int, end: int, used: int, limit: int, breaks: PhraseBreaks) -> float:
    if end == len(words):
        short = max(0.0, limit * _SHORT_LAST - used) / limit
        return short * short * _SHORT_LAST_COST + (_WIDOW if end - start == 1 else 0.0)
    slack = (limit - used) / limit
    return slack * slack * _FULL + _end_cost(words[end - 1], words[end], breaks)


def _end_cost(word: str, following: str, breaks: PhraseBreaks) -> float:
    """What ending a line on `word`, `following` opening the next, costs (negative: earns)."""
    plain = word.lower().translate(_APOSTROPHE).rstrip(_CLOSING)
    last = plain.split(" ")[-1]
    cost = 0.0
    if last in breaks.binding or _elided(last, breaks) in breaks.binding or last.endswith("'"):
        cost += _BINDING
    elif _elided(last, breaks) in breaks.auxiliaries:
        cost += _BINDING * _AUXILIARY
    head = following.lower().translate(_APOSTROPHE).lstrip(_OPENING).split(" ")[0]
    if head in breaks.clause_openers or _elision(head, breaks) in breaks.clause_openers:
        cost -= _CLAUSE * _OPENER
    elif head in breaks.prepositions:
        cost -= _CLAUSE * _PREPOSITION
    if plain.endswith((",", ";", "...", "…")):
        cost -= _CLAUSE
    return cost


def _elision(word: str, breaks: PhraseBreaks) -> str:
    """The elided prefix `word` starts with ("qu'" of "qu'il"), or ""."""
    return next((prefix for prefix in breaks.elisions if word.startswith(prefix) and word != prefix), "")


def _elided(word: str, breaks: PhraseBreaks) -> str:
    """`word` without its elided prefix: "à" of "qu'à"."""
    return word[len(_elision(word, breaks)) :]
