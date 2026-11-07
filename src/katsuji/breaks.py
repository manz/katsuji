"""A sentence broken over a set number of lines the way TeX fills a paragraph: full lines, not balanced ones.

Dynamic programming over the word positions, as Knuth and Plass break a paragraph, on a cost per line:

- a line's slack, squared, so the lines stay full;
- ending on one of the typography's `short_words` ("à" in French) costs, a guideline more than a rule: a
  much fuller line still wins;
- the last line costs when it is very short, a little more when it is a single word.

The weights were tuned on ff4's French script against a blind reading test.
"""

from collections.abc import Callable, Collection, Sequence

_FULL = 100.0
"""A line's cost per squared fraction of the width left empty."""
_SHORT_WORD = 60.0
"""A line ending on a short word."""
_SHORT_LAST = 0.4
"""Of the width: a last line narrower costs."""
_SHORT_LAST_COST = 400.0
_WIDOW = 20.0
"""A last line of one word."""
_CLOSING = "»” "
_APOSTROPHES = "'\u2019"


def break_by_cost(
    words: Sequence[str],
    lines: int,
    width: Callable[[int, int], int],
    limit: int,
    short_words: Collection[str] = (),
    first_words: int = 1,
) -> list[int] | None:
    """Where `words` end each of `lines` lines, the cheapest way: the index after each line's last word. `words`
    are plain (tags off), `width(i, j)` measures `words[i:j]` set as a line, `limit` is the widest a line may be,
    `short_words` (lower case) should not end a line, and the first line takes at least `first_words` (2 keeps
    a speaker label off a line of its own). None when no break gives `lines` lines that fit."""
    count = len(words)
    best: list[list[float | None]] = [[None] * (lines + 1) for _ in range(count + 1)]
    back: dict[tuple[int, int], int] = {}
    best[0][0] = 0.0
    for end in range(1, count + 1):
        for line in range(1, lines + 1):
            for start in range(end - 1, -1, -1):
                ahead = best[start][line - 1]
                if ahead is None:
                    continue
                used = width(start, end)
                if used > limit:
                    break
                if start == 0 and end < min(first_words, count):
                    continue
                cost = ahead + _line_cost(words, start, end, used, limit, short_words)
                current = best[end][line]
                if current is None or cost < current:
                    best[end][line] = cost
                    back[(end, line)] = start
    if best[count][lines] is None:
        return None
    ends, end = [], count
    for line in range(lines, 0, -1):
        ends.append(end)
        end = back[(end, line)]
    return ends[::-1]


def _line_cost(
    words: Sequence[str], start: int, end: int, used: int, limit: int, short_words: Collection[str]
) -> float:
    if end == len(words):
        short = max(0.0, limit * _SHORT_LAST - used) / limit
        return short * short * _SHORT_LAST_COST + (_WIDOW if end - start == 1 else 0.0)
    slack = (limit - used) / limit
    return slack * slack * _FULL + (_SHORT_WORD if _ends_short(words[end - 1], short_words) else 0.0)


def _ends_short(word: str, short_words: Collection[str]) -> bool:
    """`word` is a short word, or ends on one after an elision ("jusqu'à")."""
    last = word.lower().rstrip(_CLOSING)
    for apostrophe in _APOSTROPHES:
        last = last.rsplit(apostrophe, 1)[-1]
    return last in short_words
