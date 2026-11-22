"""snes.ninja script files (`<sn:script>` of `<sn:pointer id="…">` text), read and written in place.

Every game's dump writes its messages so (one file a bank, a list, a menu…). A pointer may carry facts about its
message as attributes, read by the tools that use them:

- `unused="1"`: no script shows it;
- `shows="KEY"`: the game shows another message in its place (a duplicate bank playing its original's table);
- `frame="menu"`: how it is drawn, when not as dialog (a frame the game names: `menu`, `battle`…);
- `speaker`, `choice`, `trigger`, `window`…: what a game's walker found.

Writing replaces one pointer's text and nothing else: the comments, the attributes and the layout of the file stay
as they were. A pointer not in the file is inserted before the first one whose id sorts after it.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, unescape

POINTER = re.compile(r'<sn:pointer id="(?P<id>[^"]*)"(?P<attributes>[^>]*)>(?P<text>.*?)</sn:pointer>', re.DOTALL)
ATTRIBUTE = re.compile(r'([\w:-]+)="([^"]*)"')
END = "</sn:script>"
COMMENT_ABOVE = re.compile(r"<!--(?:(?!-->).)*-->[ \t]*\n[ \t]*\Z", re.DOTALL)
ENTITIES = {"&quot;": '"', "&apos;": "'"}


@dataclass(frozen=True)
class Message:
    """A pointer of a script file: the file's name (no suffix), its id, its text and attributes."""

    file: str
    id: str
    text: str
    attributes: Mapping[str, str] = field(default_factory=dict)


def read(path: Path) -> list[Message]:
    """The pointers of `path`, in file order."""
    return [
        Message(path.stem, match["id"], unescape(match["text"], ENTITIES), dict(ATTRIBUTE.findall(match["attributes"])))
        for match in POINTER.finditer(path.read_text(encoding="utf-8"))
    ]


def write(path: Path, id: str, text: str) -> None:
    """Set pointer `id`'s text in `path`, inserting the pointer in id order when the file has none."""
    document = path.read_text(encoding="utf-8")
    path.write_text(replaced(document, id, text), encoding="utf-8")


def replaced(document: str, id: str, text: str) -> str:
    """`document` with pointer `id`'s text set to `text`."""
    escaped = escape(text)
    found = list(POINTER.finditer(document))
    for match in found:
        if match["id"] == id:
            return document[: match.start("text")] + escaped + document[match.end("text") :]
    element = f'<sn:pointer id="{id}">{escaped}</sn:pointer>'
    gap = _gap(document, found)
    for match in found:
        if natural(match["id"]) > natural(id):
            at = _with_comment(document, match.start())
            return document[:at] + element + gap + document[at:]
    at = document.rindex(END)
    return document[:at] + element + gap + document[at:]


def natural(id: str) -> tuple[tuple[int, int | str], ...]:
    """`id` sorted as its numbers read: "45:12" before "45:100"."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"(\d+)", id) if part)


def _with_comment(document: str, start: int) -> int:
    """Where the pointer at `start` begins, a comment just above it (a walker's note on it) included."""
    above = COMMENT_ABOVE.search(document, 0, start)
    return above.start() if above else start


def _gap(document: str, found: list[re.Match[str]]) -> str:
    """What the file sets between two pointers: a newline, or a blank line."""
    if len(found) < 2:
        return "\n"
    between = document[found[0].end() : found[1].start()]
    return "\n\n" if between.count("\n") > 1 else "\n"
