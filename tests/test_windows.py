"""`windows`: paragraphs poured into fixed-size windows. A monospace font keeps the widths readable: every
character is one pixel, a tag none."""

import re

from katsuji.dialog import Window
from katsuji.layout import TextLayout
from katsuji.typeset import ENGLISH, FRENCH, FRENCH_PHRASE_BREAKS
from katsuji.windows import Paragraph, windows


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line))


LAYOUT = TextLayout(monospace, 20, ENGLISH)
TWO_LINES = Window(20, 2)


def test_no_paragraph_makes_no_window() -> None:
    assert windows(LAYOUT, [], TWO_LINES) == []


def test_sentences_share_a_line_while_they_fit() -> None:
    assert windows(LAYOUT, [Paragraph(["One.", "Two."])], TWO_LINES) == [["One. Two."]]


def test_a_sentence_that_does_not_fit_after_the_line_takes_the_next() -> None:
    assert windows(LAYOUT, [Paragraph(["One two three.", "Four five."])], TWO_LINES) == [
        ["One two three.", "Four five."]
    ]


def test_a_new_paragraph_starts_a_new_line() -> None:
    assert windows(LAYOUT, [Paragraph(["One."]), Paragraph(["Two."])], TWO_LINES) == [["One.", "Two."]]


def test_a_paragraph_can_open_its_own_window() -> None:
    paragraphs = [Paragraph(["One."]), Paragraph(["Two."], new_window=True)]
    assert windows(LAYOUT, paragraphs, TWO_LINES) == [["One."], ["Two."]]


def test_a_new_window_opening_the_text_leaves_no_empty_window() -> None:
    assert windows(LAYOUT, [Paragraph(["One."], new_window=True)], TWO_LINES) == [["One."]]


def test_the_lead_opens_the_paragraph() -> None:
    assert windows(LAYOUT, [Paragraph(["Hi.", "Yo."], lead="Al: ")], TWO_LINES) == [["Al: Hi. Yo."]]


def test_the_lead_opens_every_window_the_paragraph_carries_onto() -> None:
    sentences = ["One two three.", "Four five six.", "Seven eight."]
    assert windows(LAYOUT, [Paragraph(sentences, lead="Al: ")], TWO_LINES) == [
        ["Al: One two three.", "Four five six."],
        ["Al: Seven eight."],
    ]


def test_a_narrower_line_turns_the_window_before_it() -> None:
    arrow = Window(20, 2, line_widths={1: 9})
    assert windows(LAYOUT, [Paragraph(["One two three.", "Four five."])], arrow) == [
        ["One two three."],
        ["Four five."],
    ]


def test_a_sentence_longer_than_a_window_breaks_over_windows() -> None:
    sentence = "aaaa bbbb cccc dddd eeee ffff gggg hhhh iiii jjjj."
    laid = windows(LAYOUT, [Paragraph([sentence])], TWO_LINES)
    assert len(laid) > 1
    assert all(len(window) <= 2 and all(monospace(line) <= 20 for line in window) for window in laid)
    assert " ".join(line for window in laid for line in window) == sentence


def test_a_long_sentence_opens_a_window_rather_than_finish_the_open_one() -> None:
    sentence = "aaaa bbbb cccc dddd eeee ffff gggg hhhh."
    laid = windows(LAYOUT, [Paragraph(["One."]), Paragraph([sentence])], TWO_LINES)
    assert laid[0] == ["One."]


def test_measure_after_sees_the_windows_laid_out_ahead() -> None:
    """A `[wide]` switch in the first window doubles every later line's width: the second window's sentences no
    longer share a line."""

    def wide_after_switch(line: str, before: str) -> int:
        return monospace(line) * (2 if "[wide]" in before + line else 1)

    layout = TextLayout(monospace, 10, ENGLISH, measure_after=wide_after_switch)
    paragraphs = [Paragraph(["[wide]Hi."]), Paragraph(["One.", "Two."], new_window=True)]
    assert windows(layout, paragraphs, TWO_LINES) == [["[wide]Hi."], ["One.", "Two."]]


def test_a_sentence_never_joins_the_last_line_of_one_that_broke() -> None:
    paragraphs = [Paragraph(["One two three four five six.", "Go."])]
    assert windows(LAYOUT, paragraphs, Window(20, 3)) == [["One two three", "four five six.", "Go."]]


def test_a_sentence_too_wide_for_a_narrower_line_is_set_again_to_it_before_the_window_turns() -> None:
    layout = TextLayout(monospace, 20, ENGLISH, min_balanced_width=20)
    paragraphs = [Paragraph(["One."]), Paragraph(["aaaa bbbb cccc dddd eeee."])]
    assert windows(layout, paragraphs, Window(20, 3, line_widths={1: 15})) == [["One.", "aaaa bbbb cccc", "dddd eeee."]]


def test_a_sentence_takes_a_spare_line_where_the_window_has_room() -> None:
    layout = TextLayout(monospace, 36, FRENCH, phrase_breaks=FRENCH_PHRASE_BREAKS, spare_lines=1)
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    assert windows(layout, [Paragraph([text])], Window(lines=4, width=36)) == [
        ["Mais le passage vers Fabul", "par le mont Hobs est bloqué", "par la glace..."]
    ]


def test_no_spare_line_is_taken_where_the_window_is_full() -> None:
    layout = TextLayout(monospace, 36, FRENCH, phrase_breaks=FRENCH_PHRASE_BREAKS, spare_lines=1)
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    laid = windows(layout, [Paragraph(["Un."]), Paragraph(["Deux."]), Paragraph([text])], Window(lines=4, width=36))
    assert laid[0][2:] == ["Mais le passage vers Fabul par le", "mont Hobs est bloqué par la glace..."]


def test_no_spare_line_is_taken_where_it_would_crowd_out_the_next_sentence() -> None:
    layout = TextLayout(monospace, 36, FRENCH, phrase_breaks=FRENCH_PHRASE_BREAKS, spare_lines=1)
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    laid = windows(layout, [Paragraph(["Un.", text]), Paragraph(["Deux trois."])], Window(lines=4, width=36))
    assert laid == [["Un.", "Mais le passage vers Fabul par le", "mont Hobs est bloqué par la glace...", "Deux trois."]]


def test_a_spare_line_is_taken_before_a_paragraph_opening_its_own_window() -> None:
    layout = TextLayout(monospace, 36, FRENCH, phrase_breaks=FRENCH_PHRASE_BREAKS, spare_lines=1)
    text = "Mais le passage vers Fabul par le mont Hobs est bloqué par la glace..."
    laid = windows(layout, [Paragraph([text]), Paragraph(["Deux."], new_window=True)], Window(lines=4, width=36))
    assert laid[0] == ["Mais le passage vers Fabul", "par le mont Hobs est bloqué", "par la glace..."]
