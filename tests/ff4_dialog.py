"""ff4's French script conventions, written on katsuji's `WindowBuilder`.

This is consumer code, the way ff4 itself will drive katsuji: its tokenizer
(`Name:` speakers, «» quotes, sentences ending on `.!?` before a capital,
`M.` not ending one) and its window rules (a quote that answers a speaker gets
its own window, a speaker change opens a new one). It lives in the tests to
prove the builder is enough; `test_dialog_ff4.py` runs ff4's goldens on it.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from katsuji.dialog import TextTable, Window, WindowBuilder
from katsuji.wrap import Wrapper

ENDS = ("[end]", "[close_window]")
SPEAKER = re.compile(r"(\w+(?:\s+\w+)*):")
QUOTE = re.compile(r"«[^»]*»")
CONTROL = re.compile(r"\[[^\]]*\]")
STRIP = ("[bold]", "[normal]", "[book]", "[wicked]")


@dataclass(frozen=True)
class Token:
    kind: str  # SPEAKER, QUOTE, SENTENCE, END, BREAK
    value: str


def tokenize(text: str) -> list[Token]:
    text = re.sub(r"\s+", " ", text.strip())
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        end = next((e for e in ENDS if text.startswith(e, i)), None)
        if end:
            tokens.append(Token("END", end))
            i += len(end)
        elif quote := QUOTE.match(text, i):
            tokens.append(Token("QUOTE", quote.group(0)))
            i = quote.end()
        elif speaker := SPEAKER.match(text, i):
            tokens.append(Token("SPEAKER", speaker.group(1)))
            i = speaker.end()
            while i < len(text) and text[i] in ": ":
                i += 1
        else:
            sentence, i = _sentence(text, i)
            if sentence.strip():
                tokens.append(Token("SENTENCE", sentence.strip()))
    return tokens


def _interrupts(text: str, i: int) -> bool:
    return text.startswith("«", i) or bool(SPEAKER.match(text, i)) or any(text.startswith(e, i) for e in ENDS)


def _sentence(text: str, i: int) -> tuple[str, int]:
    sentence = ""
    while i < len(text):
        if sentence.strip() and _interrupts(text, i):
            break
        char = text[i]
        sentence += char
        i += 1
        if char not in ".!?" or (char == "." and sentence.endswith("M.")):
            continue
        if i >= len(text) or any(text.startswith(e, i) for e in ENDS):
            break
        if text[i] == "[" and (close := text.find("]", i)) != -1:
            sentence += text[i : close + 1]
            i = close + 1
            continue
        if text[i].isspace():
            ahead = i
            while ahead < len(text) and text[ahead].isspace():
                ahead += 1
            if ahead < len(text) and (text[ahead].isupper() or _interrupts(text, ahead)):
                break
        elif SPEAKER.match(text, i):
            break
    return sentence, i


def _control_only(text: str) -> bool:
    return not CONTROL.sub("", text).strip()


def with_breaks(tokens: Sequence[Token]) -> list[Token]:
    """A break after a quote followed by more speech, and before a quote answering a speaker."""
    out: list[Token] = []
    speaking = False
    for index, token in enumerate(tokens):
        out.append(token)
        speaking = token.kind == "SPEAKER" or (speaking and token.kind not in ("QUOTE", "END"))
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if following is None:
            continue
        visible = following.kind == "SENTENCE" and not _control_only(following.value)
        if (token.kind == "QUOTE" and (following.kind in ("SPEAKER", "QUOTE") or visible)) or (
            token.kind == "SENTENCE" and speaking and following.kind == "QUOTE"
        ):
            out.append(Token("BREAK", ""))
    return out


def clean(text: str) -> str:
    """Strip the markup formatting adds, so formatting twice changes nothing."""
    cleaned = text.replace("[new]\n", "\n")
    for tag in STRIP:
        cleaned = cleaned.replace(tag, "")
    return re.sub(r"\n\s*\n", "\n", cleaned.replace("[new]", ""))


def format_dialog(text: str, table: TextTable, wrapper: Wrapper) -> str:
    """ff4's `process_dialogue`."""
    if not text:
        return text
    windows = WindowBuilder(table, wrapper, Window(208, 4, line_widths={3: 200}))
    speaker: str | None = None
    tokens = with_breaks(tokenize(clean(text)))
    for index, token in enumerate(tokens):
        if token.kind == "BREAK":
            windows.break_window()
            speaker = None
        elif token.kind == "SPEAKER":
            windows.break_window(marker=speaker is not None)
            speaker = f"[bold]{token.value}[normal]"
        elif token.kind == "SENTENCE":
            if _control_only(token.value) and not windows.filling and windows.windows:
                windows.append(token.value)
            else:
                windows.add(f"{speaker}: {token.value}" if speaker and not windows.filling else token.value)
        elif token.kind == "QUOTE":
            breaks = index + 1 < len(tokens) and tokens[index + 1].kind == "BREAK"
            windows.emit(token.value, marker=breaks)
            speaker = None
        else:  # END
            windows.append(token.value)
            windows.break_window(marker=False)
            speaker = None
    return "\n".join(windows.result())
