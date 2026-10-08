"""Typography: the spaces a language puts around punctuation, applied to a game's script.

What a language spaces is data (`Typography`, `ENGLISH`, `FRENCH`); how a game
writes its tags is the game's (`Markup`). Shared by every language: a space
after a comma that runs into the next word (never inside a number: 1,5) and
after an ellipsis that runs into it ("Hmm... yes"; one opening the line or
following a tag resumes it, "...yes"), single spaces between words,
the indentation left alone.

Tags are atomic. One that reads as a word (a name) is spaced like a word; a
raw glyph code keeps the mark after it tight; any other tag is a control
(a terminator, a wait) and nothing is spaced before it.
"""

import re
from dataclasses import dataclass

WORD = "\ue000"
GLYPH = "\ue001"
CONTROL = "\ue002"
_PLACEHOLDER = re.compile(f"[{WORD}{GLYPH}{CONTROL}]")
_COMMA = re.compile(rf",(?=[^\s\d{CONTROL}])|(?<=\D),(?=\d)")
_ELLIPSIS = re.compile(rf"(?<=[^.{WORD}{GLYPH}{CONTROL}])(\.\.\.+)(?![\s.?!,;:»\"')\u201d\u2019{CONTROL}]|$)")
_SPEAKER = re.compile(r"[^\s:.?!,]+(?: [^\s:.?!,]+){0,2}:")  # "Roi de Kana:"
_SPACES = re.compile(r"(?<=\S)  +(?=\S)")


@dataclass(frozen=True)
class Typography:
    """The marks a language sets apart from the word they touch."""

    space_before: str = ""
    """Marks with a space before them; a run of them ("?!") takes one."""
    quotes: str = ""
    """Opening and closing quote, spaced inside: French « ... »."""

    @property
    def glued(self) -> str:
        """Marks a line may never start with: the space before them must not break it."""
        return self.space_before + self.quotes[1:]


ENGLISH = Typography()
FRENCH = Typography(space_before="?!;:", quotes="«»")


@dataclass(frozen=True)
class Markup:
    """How a game's script writes its tags, as regular expressions.

    bahamut_lagoon: `Markup(tag=r"\\[character\\]\\[0x[0-9a-f]+\\]|\\[[^]]*\\]",
    words=r"\\[character\\].*", glyphs=r"\\[0x[0-9a-f]+\\]", speakers=True)`.
    """

    tag: str = r"\[[^\]]*\]"
    """One tag: matched first, never split or spaced inside."""
    words: str | None = None
    """Tags that read as a word (names)."""
    glyphs: str | None = None
    """Tags that draw a glyph: a mark after them stays tight."""
    speakers: bool = False
    """A speaker opening the line ("Yoyo:") keeps its colon as written."""

    def kind(self, tag: str) -> str:
        if self.words and re.fullmatch(self.words, tag, re.IGNORECASE):
            return WORD
        if self.glyphs and re.fullmatch(self.glyphs, tag, re.IGNORECASE):
            return GLYPH
        return CONTROL


def typeset(text: str, typography: Typography, markup: Markup | None = None) -> str:
    """`text` spaced the way `typography` says, line by line, its tags read with `markup`."""
    markup = markup or Markup()
    return "\n".join(_typeset_line(line, typography, markup) for line in text.split("\n"))


def _typeset_line(line: str, typography: Typography, markup: Markup) -> str:
    if _PLACEHOLDER.search(line):
        raise ValueError(f"private-use character in {line!r}")
    tags = [match[0] for match in re.finditer(markup.tag, line, re.IGNORECASE)]
    text = re.sub(markup.tag, lambda match: markup.kind(match[0]), line, flags=re.IGNORECASE)
    indent = text[: len(text) - len(text.lstrip(" "))]
    text = _spaced(text[len(indent) :], typography, markup.speakers)
    restored = iter(tags)
    return _PLACEHOLDER.sub(lambda _: next(restored), indent + text)


def _spaced(text: str, typography: Typography, speakers: bool) -> str:
    text = _ELLIPSIS.sub(r"\1 ", _COMMA.sub(", ", text))
    speaker = _SPEAKER.match(text) if speakers else None
    head = text[: speaker.end()] if speaker else ""
    rest = _space_before(text[len(head) :], typography.space_before)
    if typography.quotes:
        rest = _space_before(_space_after(rest, typography.quotes[0]), typography.quotes[1])
    return _SPACES.sub(" ", head + rest)


def _space_before(text: str, marks: str) -> str:
    """A space before each run of `marks` that touches what precedes it; after a glyph code, none."""
    out = []
    for index, char in enumerate(text):
        if char in marks and index and text[index - 1] not in " " + marks + GLYPH:
            out.append(" ")
        out.append(char)
    return "".join(out)


def _space_after(text: str, marks: str) -> str:
    """A space after each of `marks` that touches what follows it."""
    out = []
    for index, char in enumerate(text):
        out.append(char)
        if char in marks and index + 1 < len(text) and text[index + 1] != " ":
            out.append(" ")
    return "".join(out)
