"""`break_by_cost` and `TextLayout(fill=True)`: a sentence filled over lines the way TeX fills a paragraph. A
monospace font keeps the widths readable: every character is one pixel, a tag none."""

import re
from dataclasses import replace

from katsuji.breaks import break_by_cost
from katsuji.layout import TextLayout
from katsuji.typeset import ENGLISH, FRENCH, FRENCH_ONE_LETTER_WORDS

FRENCH_TYPESET = replace(FRENCH, short_words=FRENCH_ONE_LETTER_WORDS)


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line))


def filled(width: int, **options: object) -> TextLayout:
    return TextLayout(monospace, width, FRENCH_TYPESET, fill=True, **options)  # type: ignore[arg-type]


def lines(layout: TextLayout, text: str) -> list[str]:
    return [line for block in layout.blocks(text) for line in block]


def ends(words: str, count: int, limit: int, first_words: int = 1) -> list[int] | None:
    split = words.split(" ")

    def width(start: int, end: int) -> int:
        return len(" ".join(split[start:end]))

    return break_by_cost(split, count, width, limit, set(FRENCH_ONE_LETTER_WORDS), first_words)


def test_the_first_line_is_filled_not_balanced() -> None:
    assert lines(filled(28), "Caïn : Je me doutais que tu allais dire ça.") == [
        "Caïn : Je me doutais que tu",
        "allais dire ça.",
    ]


def test_balancing_would_leave_the_first_line_short() -> None:
    assert lines(TextLayout(monospace, 28, FRENCH), "Caïn : Je me doutais que tu allais dire ça.")[0] != (
        "Caïn : Je me doutais que tu"
    )


def test_a_line_does_not_end_on_a_one_letter_word() -> None:
    assert lines(filled(33), "Nous devons partir vers le nord à l'aube pour rejoindre Fabul.") == [
        "Nous devons partir vers le nord",
        "à l'aube pour rejoindre Fabul.",
    ]


def test_without_short_words_it_fills_regardless() -> None:
    layout = TextLayout(monospace, 33, FRENCH, fill=True)
    assert lines(layout, "Nous devons partir vers le nord à l'aube pour rejoindre Fabul.")[0].endswith(" à")


def test_a_short_word_ends_a_line_when_keeping_it_off_overflows() -> None:
    assert ends("abcdefghi à bc defghij", 2, 11) == [2, 4]


def test_an_elided_short_word_is_kept_off_like_the_full_one() -> None:
    assert lines(filled(24), "Il reste peu jusqu'à demain matin et nous partirons ensemble.")[0] == "Il reste peu"


def test_a_typographic_apostrophe_counts_like_the_straight_one() -> None:
    assert lines(filled(24), "Il reste peu jusqu\u2019à demain matin et nous partirons ensemble.")[0] == "Il reste peu"


def test_a_speaker_label_never_stands_alone() -> None:
    assert ends("Cid: abcdefghij", 2, 11, first_words=2) is None


def test_the_first_line_may_take_one_word_without_a_label() -> None:
    assert ends("Cid: abcdefghij", 2, 11) == [1, 2]


def test_a_last_line_of_one_short_word_is_avoided() -> None:
    assert lines(filled(28), "Nous partirons vers le nord tous ensemble, oui.") == [
        "Nous partirons vers le nord",
        "tous ensemble, oui.",
    ]


def test_it_takes_as_many_lines_as_greedy_filling() -> None:
    text = "Disparaissez dans les ténèbres avant même de m'atteindre !"
    assert len(lines(filled(20), text)) == len(lines(TextLayout(monospace, 20, FRENCH), text))


def test_laying_out_twice_changes_nothing() -> None:
    text = "Rosa : Dieu merci, tu es sain et sauf ! Je craignais le pire pour toi."
    once = "\n".join(lines(filled(22), text))
    assert "\n".join(lines(filled(22), once)) == once


def test_no_break_fits_a_word_wider_than_a_line() -> None:
    assert ends("ab abcdefghijkl", 2, 10) is None


def test_a_switch_held_across_a_break_falls_back_to_balancing() -> None:
    """The breaker measures from the sentence's start; a `[wide]` switch doubling the lines after it overflows
    the second line, measured line after line, so the balanced breaker takes over."""

    def wide_after_switch(line: str, before: str) -> int:
        return monospace(line) * (2 if "[wide]" in before else 1)

    layout = filled(20, measure_after=wide_after_switch)
    text = "Un deux trois quatre, cinq six [wide]sept."
    assert lines(layout, text) == lines(
        TextLayout(monospace, 20, FRENCH_TYPESET, measure_after=wide_after_switch), text
    )


def test_a_word_wider_than_a_line_falls_back_to_balancing() -> None:
    text = "Ab abcdefghijkl cd."
    assert lines(filled(10), text) == lines(TextLayout(monospace, 10, FRENCH_TYPESET), text)


def test_a_speaker_label_of_several_words_never_stands_alone() -> None:
    layout = TextLayout(monospace, 20, ENGLISH, fill=True)
    assert lines(layout, "Femme de Yang: tu sais, aaaaaaaaaaaaaaaaa.")[0] != "Femme de Yang:"


def test_a_short_last_line_of_two_words_is_free() -> None:
    """ "C'est comme si j'avais tué / ta mère...": the first line stays full, the last short."""
    assert filled(26).reflow("cccc cccc cc cccc cccc cc cccc.") == "cccc cccc cc cccc cccc\ncc cccc."
