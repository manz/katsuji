"""Dialog laid out to its window: paragraphs reflowed by sentences, lines placed, blocks kept within a window.

The game gives how wide a line draws (`measure`: its encoder, names at their
widest), the window's width, its typography and which lines its script keeps
as written. Everything else is shared:

- A paragraph's lines are joined and wrapped again by sentences: sentences
  share a line while they fit, one that does not starts its own, and one wider
  than the window breaks at spaces over as few, balanced, lines as it needs.
- Kept as written: blank lines (they separate paragraphs), speaker labels and
  headings alone on their line, lines starting with one space (choices).
  A numbered item is a paragraph of its own.
  Lines starting with two or more are placed: centred, or right-aligned when
  set well right of the middle (a signature).
- `paginate`: a block of lines never crosses into the next window, a speaker
  label stays with the block after it.

bahamut_lagoon's French dialog is the reference: utils/dialog_layout.py.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from katsuji.typeset import CONTROL, ENGLISH, Markup, Typography, typeset

Measure = Callable[[str], int]
"""A line's width in pixels as the engine writes it, compared against the window's width.

Whether that counts the blank gap after the last glyph is the engine's: one
that writes the gap column needs `Wrapper.measure` as is (gap included), one
that only ORs ink into the line needs `Wrapper.measure(...) - gap`."""
Block = list[str]
"""Lines that go into one window together."""

SENTENCE_ENDS = ".!?…"
BREAK = "\ue003"  # after a paragraph break, between typesetting and layout


@dataclass(frozen=True)
class TextLayout:
    """Lays dialog out to a window `width` pixels wide."""

    measure: Measure
    width: int
    typography: Typography = ENGLISH
    markup: Markup = field(default_factory=Markup)
    labels: str | None = None
    """A speaker label alone on its line ("Yoyo:"): kept, and kept with the block after it."""
    headings: str | None = None
    """A heading alone on its line ("-Aller-"): kept."""
    placed_measure: Measure | None = None
    """Where a line sits, as opposed to how wide it may grow: names at their default spelling."""
    breaks: str | None = None
    """A tag that ends its paragraph ("[WAIT]"): what follows it starts a new line, even on the same one. Matched
    over the whole text, so `$` is the text's end: `\\[WAIT\\](?!(?:\\[[^]]*\\])*$)` skips a [WAIT] closing it."""
    speaker: str | None = None
    """A speaker opening a paragraph ("[D4]Soldier: "): its continuation lines hang `hanging` spaces in, whatever
    their indent in the source."""
    hanging: int = 2
    items: str | None = None
    """A numbered line ("1- "): a paragraph of its own, wrapped but never joined to the lines around it."""
    right_of_centre: int = 10
    """Pixels: an indented line set further right than this is right-aligned."""
    min_balanced_width: int = 0
    """Pixels: a balanced sentence's lines are never set narrower, so one just over a line does not become two
    half-empty ones (bahamut_lagoon: two thirds of the window)."""

    def reflow(self, text: str, page_lines: int | None = None) -> str:
        """`text` typeset, then laid out to the window; given the window's `page_lines`, paginated."""
        blocks = self.blocks(text)
        if page_lines is not None:
            blocks = self.paginate(blocks, page_lines)
        return "\n".join(line for block in blocks for line in block)

    def blocks(self, text: str) -> list[Block]:
        """`text` typeset and laid out, as the blocks `paginate` keeps within a window."""
        lines = self._mark_breaks(typeset(text, self.typography, self.markup)).split("\n")
        indented = [line for line in lines if line.startswith("  ") and line.strip()]
        block_indent = len(indented) > 1 and len({len(line) - len(line.lstrip(" ")) for line in indented}) == 1
        blocks: list[Block] = []
        paragraph: list[str] = []

        def close_paragraph() -> None:
            if paragraph:
                blocks.extend(self._wrap_paragraph(" ".join(paragraph), self._hanging(paragraph[0])))
                paragraph.clear()

        for marked in lines:
            if marked.startswith(" ") and paragraph and self._hanging(paragraph[0]) is not None:
                marked = marked.lstrip(" ")  # a speaker's continuation: its indent is set again
            line = marked.replace(BREAK, "")
            if not line.strip():
                close_paragraph()
                blocks.append([""])  # a spacer, spaces or not, draws nothing
            elif line.startswith(" ") or self._kept(line):
                close_paragraph()
                blocks.append([line if block_indent else self.place(line)])
            elif self.items and re.match(self.items, line):
                close_paragraph()
                blocks.extend(self._wrap_paragraph(line))
            else:
                *closed, rest = marked.split(BREAK)
                for piece in closed:
                    paragraph.append(piece.lstrip(" "))
                    close_paragraph()
                if rest.strip():
                    paragraph.append(rest.lstrip(" "))
        close_paragraph()
        return blocks

    def paginate(self, blocks: list[Block], page_lines: int) -> list[Block]:
        """`blocks` laid over windows of `page_lines` lines: a block that would cross into the next window is
        pushed there by blank lines, a speaker label stays with the block after it, and a blank line that would
        open a window is dropped."""
        out: list[Block] = []
        row = 0
        pending_label: Block = []
        for block in blocks:
            if block == [""] and not pending_label:
                if row % page_lines == 0 and out:
                    continue
                out.append(block)
                row += 1
                continue
            if len(block) == 1 and self._is_label(block[0]) and not pending_label:
                pending_label = block
                continue
            lines = pending_label + block
            pending_label = []
            used = row % page_lines
            if used and used + len(lines) > page_lines and len(lines) <= page_lines:
                out.append([""] * (page_lines - used))
                row += page_lines - used
            out.append(lines)
            row += len(lines)
        if pending_label:
            out.append(pending_label)
        return out

    def place(self, line: str) -> str:
        """A line starting with two spaces or more, re-indented in the window: right-aligned when it was set well
        right of the middle, else centred; within half a space, the indent's unit. Others stay as they are.
        A placed line is never wrapped: one wider than the window stays wider (`overflows` lists it)."""
        if not line.startswith("  "):
            return line
        text = line.lstrip(" ")
        space = self.measure(" ")
        width = (self.placed_measure or self.measure)(text)
        right = (len(line) - len(text)) * space + width / 2 - self.width / 2 > self.right_of_centre
        if right:
            return " " * (max(0, self.width - width) // space) + text
        return " " * round(max(0, (self.width - width) // 2) / space) + text

    def centre(self, line: str) -> str:
        """`line` centred whatever its indentation (two spaces or more)."""
        if not line.startswith("  "):
            return line
        return self.place("  " + line.lstrip(" "))

    def overflows(self, text: str) -> Iterator[tuple[str, int]]:
        """The lines of `text` wider than the window, with their width."""
        for line in text.split("\n"):
            width = self.measure(line)
            if width > self.width:
                yield line, width

    def _mark_breaks(self, text: str) -> str:
        """`text` with `BREAK` after each paragraph break, matched over the whole text (`$` is its end)."""
        if not self.breaks:
            return text
        return re.sub(self.breaks, lambda match: match[0] + BREAK, text, flags=re.IGNORECASE)

    def _kept(self, line: str) -> bool:
        return self._is_label(line) or bool(self.headings and re.fullmatch(self.headings, line))

    def _is_label(self, line: str) -> bool:
        return bool(self.labels and re.fullmatch(self.labels, line))

    def _hanging(self, first_line: str) -> str | None:
        """The indent of a paragraph's continuation lines when it opens with a speaker."""
        if self.speaker and re.match(self.speaker, first_line, re.IGNORECASE):
            return " " * self.hanging
        return None

    def _wrap_paragraph(self, text: str, indent: str | None = None) -> list[Block]:
        """`text` by sentences: sentences share a line while they fit, a sentence that does not fit after the line
        so far starts its own, and one wider than the window breaks at spaces into its own block, its last line
        taking no further sentence. Lines after the first start with `indent`, measured with it."""
        indent = indent or ""
        blocks: list[Block] = []
        current = ""
        for sentence in self._sentences(text):
            lead = indent if blocks else ""
            candidate = f"{current} {sentence}" if current else lead + sentence
            if self.measure(candidate) <= self.width:
                current = candidate
                continue
            if current:
                blocks.append([current])
                lead = indent
            if self.measure(lead + sentence) <= self.width:
                current = lead + sentence
            else:
                blocks.append(self._break_words(sentence, lead, indent))
                current = ""
        if current:
            blocks.append([current])
        return blocks

    def _words(self, text: str) -> list[str]:
        """Words, with a mark the line may not start with (French ? ! ; : ») kept on the word before it."""
        words: list[str] = []
        for word in text.split(" "):
            if words and word[:1] and word[0] in self.typography.glued:
                words[-1] += f" {word}"
            else:
                words.append(word)
        return words

    def _sentences(self, text: str) -> list[str]:
        """`text` cut after each word ending a sentence."""
        sentences: list[str] = []
        current: list[str] = []
        for word in self._words(text):
            current.append(word)
            if self._ends_sentence(word):
                sentences.append(" ".join(current))
                current = []
        if current:
            sentences.append(" ".join(current))
        return sentences

    def _ends_sentence(self, word: str) -> bool:
        """`word` ends in . ! ? or …, before any control tags (a terminator) and closing quote."""
        while trailing := re.search(f"(?:{self.markup.tag})$", word, re.IGNORECASE):
            if self.markup.kind(trailing[0]) != CONTROL:
                break
            word = word[: trailing.start()]
        return word.rstrip(self.typography.quotes[1:] + " ")[-1:] in set(SENTENCE_ENDS)

    def _break_words(self, sentence: str, lead: str = "", indent: str = "") -> list[str]:
        """`sentence` broken at spaces into as few lines as the window allows, balanced: the narrowest width that
        still needs no more lines, so the last line is not left with a word or two, down to `min_balanced_width`."""
        lines = self._greedy(sentence, self.width, lead, indent)
        narrow, wide = 1, self.width
        while narrow < wide:
            middle = (narrow + wide) // 2
            if len(self._greedy(sentence, middle, lead, indent)) <= len(lines):
                wide = middle
            else:
                narrow = middle + 1
        return self._greedy(sentence, max(wide, self.min_balanced_width), lead, indent)

    def _greedy(self, sentence: str, width: int, lead: str = "", indent: str = "") -> list[str]:
        """Words fill each line up to `width`, the first line after `lead`, the others after `indent`; a word that
        would pass it starts the next."""
        lines: list[str] = []
        current = lead
        for word in self._words(sentence):
            started = current.strip() != ""
            candidate = f"{current} {word}" if started else current + word
            if started and self.measure(candidate) > width:
                lines.append(current)
                current = indent + word
            else:
                current = candidate
        lines.append(current)
        return lines
