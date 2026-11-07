"""`break_by_cost` and `TextLayout(phrase_breaks=...)`: a sentence broken where its phrases part. A monospace font
keeps the widths readable: every character is one pixel, a tag none."""

import re

from katsuji.breaks import break_by_cost
from katsuji.layout import TextLayout
from katsuji.typeset import ENGLISH, FRENCH, FRENCH_PHRASE_BREAKS


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line))


def phrased(width: int, **options: object) -> TextLayout:
    return TextLayout(monospace, width, FRENCH, phrase_breaks=FRENCH_PHRASE_BREAKS, **options)  # type: ignore[arg-type]


def lines(layout: TextLayout, text: str) -> list[str]:
    return [line for block in layout.blocks(text) for line in block]


def ends(words: str, count: int, limit: int, first_words: int = 1) -> list[int] | None:
    split = words.split(" ")

    def width(start: int, end: int) -> int:
        return len(" ".join(split[start:end]))

    return break_by_cost(split, count, width, limit, FRENCH_PHRASE_BREAKS, first_words)


def test_a_line_breaks_after_the_comma_not_after_the_pronoun() -> None:
    assert lines(phrased(22), "Rosa : Dieu merci, tu es sain et sauf !") == [
        "Rosa : Dieu merci,",
        "tu es sain et sauf !",
    ]


def test_a_line_does_not_end_on_an_article() -> None:
    assert lines(phrased(18), "Il maîtrise l'art de la lame noire.") == ["Il maîtrise l'art", "de la lame noire."]


def test_a_line_does_not_end_on_an_auxiliary() -> None:
    assert lines(phrased(24), "Les soldats n'ont opposé aucune résistance.") == [
        "Les soldats n'ont opposé",
        "aucune résistance.",
    ]


def test_an_elided_preposition_binds_like_the_full_one() -> None:
    assert lines(phrased(21), "Il reste peu jusqu'à demain matin.") == ["Il reste peu", "jusqu'à demain matin."]


def test_a_typographic_apostrophe_binds_like_the_straight_one() -> None:
    assert lines(phrased(18), "Il maîtrise l\u2019art de la lame noire.") == [
        "Il maîtrise l\u2019art",
        "de la lame noire.",
    ]


def test_a_speaker_label_never_stands_alone() -> None:
    assert ends("Cid: abcdefghij", 2, 11, first_words=2) is None


def test_the_first_line_may_take_one_word_without_a_label() -> None:
    assert ends("Cid: abcdefghij", 2, 11) == [1, 2]


def test_a_last_line_of_one_word_is_avoided() -> None:
    """Greedy filling ends the first line on the comma and leaves "ensemble." alone."""
    assert lines(phrased(28), "Nous partirons vers le nord, ensemble.") == ["Nous partirons", "vers le nord, ensemble."]


def test_it_takes_as_many_lines_as_greedy_filling() -> None:
    text = "Disparaissez dans les ténèbres avant même de m'atteindre !"
    assert len(lines(phrased(20), text)) == len(lines(TextLayout(monospace, 20, FRENCH), text))


def test_laying_out_twice_changes_nothing() -> None:
    text = "Rosa : Dieu merci, tu es sain et sauf ! Je craignais le pire pour toi."
    once = "\n".join(lines(phrased(22), text))
    assert "\n".join(lines(phrased(22), once)) == once


def test_no_break_fits_a_word_wider_than_a_line() -> None:
    assert ends("ab abcdefghijkl", 2, 10) is None


def test_a_switch_held_across_a_break_falls_back_to_balancing() -> None:
    """The cost breaker measures from the sentence's start; a `[wide]` switch doubling the lines after it
    overflows the second line, measured line after line, so the balanced breaker takes over."""

    def wide_after_switch(line: str, before: str) -> int:
        return monospace(line) * (2 if "[wide]" in before else 1)

    layout = phrased(20, measure_after=wide_after_switch)
    text = "Un deux trois quatre, cinq six [wide]sept."
    assert lines(layout, text) == lines(TextLayout(monospace, 20, FRENCH, measure_after=wide_after_switch), text)


def test_a_word_wider_than_a_line_falls_back_to_balancing() -> None:
    text = "Ab abcdefghijkl cd."
    assert lines(phrased(10), text) == lines(TextLayout(monospace, 10, FRENCH), text)


def test_a_speaker_label_of_several_words_never_stands_alone() -> None:
    """The label alone, then "tu sais," ending on its comma, would cost least."""
    layout = TextLayout(monospace, 20, ENGLISH, phrase_breaks=FRENCH_PHRASE_BREAKS)
    assert lines(layout, "Femme de Yang: tu sais, aaaaaaaaaaaaaaaaa.")[0] != "Femme de Yang:"


def test_a_line_does_not_end_on_a_modal_before_its_infinitive() -> None:
    assert lines(phrased(42), "C'est ce vieux croûton qui aurait dû mourir, pas eux !") == [
        "C'est ce vieux croûton",
        "qui aurait dû mourir, pas eux !",
    ]


def spare_ends(words: str, count: int, limit: int, spare: int) -> list[int] | None:
    split = words.split(" ")

    def width(start: int, end: int) -> int:
        return len(" ".join(split[start:end]))

    return break_by_cost(split, count, width, limit, FRENCH_PHRASE_BREAKS, spare=spare)


def test_a_spare_line_is_taken_when_it_breaks_much_better() -> None:
    """On two lines the first must end on "par le"; a third line breaks before each "par"."""
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    assert spare_ends(text, 2, 36, spare=1) == [5, 11, 14]


def test_no_spare_line_is_taken_when_the_breaks_are_already_good() -> None:
    assert spare_ends("Rosa : Dieu merci, tu es sain et sauf !", 2, 22, spare=1) == [4, 10]


def test_a_layout_with_spare_lines_breaks_a_tight_sentence_over_one_more() -> None:
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    assert lines(phrased(36, spare_lines=1), text) == [
        "Mais le passage vers Fabul",
        "par le mont Hobs est bloqué",
        "par la glace...",
    ]
