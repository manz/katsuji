"""Dialog layout, with bahamut_lagoon's dialog layout cases (utils/tests/test_dialog_layout.py) as the spec.

A monospace font keeps the widths readable: every character is one pixel, a
tag none, a name ([HERO]) five.
"""

import re

import pytest

from katsuji.layout import TextLayout
from katsuji.typeset import ENGLISH, FRENCH, Markup

MARKUP = Markup(words=r"\[HERO\]")
LABEL = r"[^ ].*:"
HEADING = r"-[^ ].*-"


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line.replace("[HERO]", "HHHHH")))


def at_default(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line.replace("[HERO]", "Ho")))


@pytest.fixture
def layout() -> TextLayout:
    return TextLayout(monospace, 20, ENGLISH, MARKUP, labels=LABEL, headings=HEADING, placed_measure=at_default)


def test_short_lines_of_a_paragraph_are_joined(layout: TextLayout) -> None:
    assert layout.reflow("one two\nthree") == "one two three"


def test_short_sentences_share_a_line(layout: TextLayout) -> None:
    assert layout.reflow("Hi. Yes. Go.") == "Hi. Yes. Go."


def test_a_sentence_that_does_not_fit_after_the_line_starts_its_own(layout: TextLayout) -> None:
    assert layout.reflow("Hello there. Come along now.") == "Hello there.\nCome along now."


def test_a_line_wider_than_the_window_breaks_at_spaces(layout: TextLayout) -> None:
    assert all(width <= 20 for width in map(monospace, layout.reflow("a " * 30).split("\n")))


def test_a_long_sentence_is_balanced_over_its_lines(layout: TextLayout) -> None:
    assert layout.reflow("aaaa bbbb cccc dddd eeee ffff") == "aaaa bbbb cccc\ndddd eeee ffff"


def test_the_tail_of_a_wrapped_sentence_takes_no_other_sentence(layout: TextLayout) -> None:
    assert layout.reflow("aaaa bbbb cccc dddd eeee. Go.") == "aaaa bbbb cccc\ndddd eeee.\nGo."


def test_a_name_measures_at_its_widest(layout: TextLayout) -> None:
    assert layout.reflow("Thanks, [HERO]. Go on.") == "Thanks, [HERO].\nGo on."


def test_a_terminator_does_not_hide_a_sentence_end(layout: TextLayout) -> None:
    assert layout.reflow("Hello there.[WAIT] Come along now.") == "Hello there.[WAIT]\nCome along now."


def test_a_glyph_after_the_full_stop_is_no_sentence_end() -> None:
    layout = TextLayout(monospace, 20, ENGLISH, Markup(glyphs=r"\[0x..\]"))
    assert layout.reflow("Ok.[0xd8] aaaa bbbb cccc dddd") == "Ok.[0xd8] aaaa bbbb\ncccc dddd"


def test_a_french_mark_stays_with_its_word() -> None:
    layout = TextLayout(monospace, 12, FRENCH)
    assert layout.reflow("Tu viens oui ?") == "Tu viens\noui ?"


def test_a_closing_quote_after_the_mark_still_ends_the_sentence() -> None:
    layout = TextLayout(monospace, 20, FRENCH)
    assert layout.reflow("« Bonjour toi ! » Et alors.") == "« Bonjour toi ! »\nEt alors."


def test_blank_lines_separate_paragraphs(layout: TextLayout) -> None:
    assert layout.reflow("one\n\ntwo") == "one\n\ntwo"


def test_a_line_of_spaces_is_a_blank_line(layout: TextLayout) -> None:
    assert layout.reflow("one\n   \ntwo") == "one\n\ntwo"


def test_a_line_starting_with_one_space_is_kept(layout: TextLayout) -> None:
    assert layout.reflow("Pick:\n Yes\n No") == "Pick:\n Yes\n No"


def test_a_speaker_label_keeps_its_own_line(layout: TextLayout) -> None:
    assert layout.reflow("Yoyo:\nhi\nthere") == "Yoyo:\nhi there"


def test_a_heading_keeps_its_own_line(layout: TextLayout) -> None:
    assert layout.reflow("-Go-\nwalk on") == "-Go-\nwalk on"


def test_a_line_starting_with_two_spaces_is_centred(layout: TextLayout) -> None:
    assert layout.reflow("  Fin") == "        Fin"


def test_a_centred_name_sits_at_its_default_width(layout: TextLayout) -> None:
    assert layout.reflow("  [HERO]") == "         [HERO]"


def test_a_line_set_right_of_centre_is_right_aligned(layout: TextLayout) -> None:
    assert layout.reflow("                  -Sendack-") == "           -Sendack-"


def test_lines_sharing_one_indent_are_kept(layout: TextLayout) -> None:
    assert layout.reflow("  one\n  two") == "  one\n  two"


def test_centre_ignores_where_the_line_was_set(layout: TextLayout) -> None:
    assert layout.centre("                  Fin") == "        Fin"


def test_centre_leaves_a_line_without_indent(layout: TextLayout) -> None:
    assert layout.centre("Fin") == "Fin"


def test_a_block_that_would_cross_the_window_starts_the_next(layout: TextLayout) -> None:
    text = "aaaa bbbb cccc dddd eeee. aaaa bbbb cccc dddd eeee ffff."
    assert layout.reflow(text, page_lines=3) == "aaaa bbbb cccc\ndddd eeee.\n\naaaa bbbb cccc\ndddd eeee ffff."


def test_a_speaker_label_stays_with_its_text_across_windows(layout: TextLayout) -> None:
    assert layout.reflow("one\ntwo.\n\nYoyo:\nhi", page_lines=2) == "one two.\n\nYoyo:\nhi"


def test_a_blank_line_does_not_open_a_window(layout: TextLayout) -> None:
    text = "aaaa bbbb cccc dddd eeee ffff.\n\nthree."
    assert layout.reflow(text, page_lines=2) == "aaaa bbbb cccc\ndddd eeee ffff.\nthree."


def test_a_label_closing_the_text_is_kept(layout: TextLayout) -> None:
    assert layout.reflow("one.\nYoyo:", page_lines=3) == "one.\nYoyo:"


def test_reflowing_twice_changes_nothing(layout: TextLayout) -> None:
    once = layout.reflow("Hello there,[HERO]. Come along now...ok? aaaa bbbb cccc dddd eeee ffff.")
    assert layout.reflow(once) == once


def test_overflows_lists_lines_wider_than_the_window(layout: TextLayout) -> None:
    assert list(layout.overflows("short\n" + "x" * 21)) == [("x" * 21, 21)]


def test_a_balanced_sentence_is_set_no_narrower_than_the_floor() -> None:
    layout = TextLayout(monospace, 20, min_balanced_width=18)
    assert layout.reflow("aaaa bbbb cccc dddd ee") == "aaaa bbbb cccc\ndddd ee"


def test_without_a_floor_the_sentence_is_balanced_to_its_narrowest(layout: TextLayout) -> None:
    assert layout.reflow("aaaa bbbb cccc dddd ee") == "aaaa bbbb\ncccc dddd ee"


def test_a_numbered_item_is_a_paragraph_of_its_own() -> None:
    layout = TextLayout(monospace, 20, items=r"\d+-")
    assert layout.reflow("Pick one.\n1- red\n2- blue") == "Pick one.\n1- red\n2- blue"


def test_a_numbered_item_wider_than_the_window_still_wraps() -> None:
    layout = TextLayout(monospace, 20, items=r"\d+-")
    assert layout.reflow("1- aaaa bbbb cccc dddd") == "1- aaaa bbbb\ncccc dddd"


WAIT = r"\[WAIT\](?!\[END\])"


def test_a_break_ends_its_paragraph() -> None:
    assert TextLayout(monospace, 20, breaks=WAIT).reflow("Hi.[WAIT]\nYo.") == "Hi.[WAIT]\nYo."


def test_without_breaks_the_lines_are_joined(layout: TextLayout) -> None:
    assert layout.reflow("Hi.[WAIT]\nYo.") == "Hi.[WAIT] Yo."


def test_a_break_inside_a_line_starts_a_new_one() -> None:
    assert TextLayout(monospace, 20, breaks=WAIT).reflow("Hi.[WAIT] Yo.") == "Hi.[WAIT]\nYo."


def test_the_break_pattern_decides_what_stays_on_the_line() -> None:
    assert TextLayout(monospace, 20, breaks=WAIT).reflow("Hi.[WAIT][END]") == "Hi.[WAIT][END]"


def test_lines_after_a_break_are_joined_again() -> None:
    assert TextLayout(monospace, 20, breaks=WAIT).reflow("Hi.[WAIT]\nhow\nare you") == "Hi.[WAIT]\nhow are you"


def test_a_break_at_the_end_of_a_line_ends_it_whatever_fits() -> None:
    layout = TextLayout(monospace, 20, breaks=r"\[WAIT\](?!(?:\[[^\]]*\])*$)")
    assert layout.reflow("A.[WAIT]\nB.[END]") == "A.[WAIT]\nB.[END]"


def test_a_break_pattern_sees_the_whole_text() -> None:
    layout = TextLayout(monospace, 20, breaks=r"\[WAIT\](?!(?:\[[^\]]*\])*$)")
    assert layout.reflow("A.[WAIT]\nB.[WAIT][END]") == "A.[WAIT]\nB.[WAIT][END]"


SPEAKER = r"(?:\[[^\]]*\])*\[D4\][^:\n]{1,24} ?: "


def test_a_speaker_s_continuation_lines_hang() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER)
    text = "[D4]Luida: A tavern where travellers gather."
    assert layout.reflow(text) == "[D4]Luida: A tavern\n  where travellers\n  gather."


def test_a_hanging_line_is_measured_with_its_indent() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER)
    assert all(monospace(line) <= 20 for line in layout.reflow("[D4]Bo: " + "aaa " * 20 + "end.").split("\n"))


def test_the_source_indent_of_a_speaker_s_lines_is_set_again() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER, hanging=1)
    assert layout.reflow("[D4]Bo: one two\n   three four five") == "[D4]Bo: one two\n three four five"


def test_each_sentence_after_the_first_line_hangs() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER)
    assert layout.reflow("[D4]Bo: Hello there. Come along now.") == "[D4]Bo: Hello there.\n  Come along now."


def test_a_paragraph_without_a_speaker_does_not_hang() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER)
    assert layout.reflow("A tavern where travellers gather.") == "A tavern where\ntravellers gather."


def test_after_a_break_the_next_speaker_hangs_on_its_own() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER, breaks=WAIT)
    text = "[D4]Bo: Hello there.[WAIT]\n[D4]Al: Come along with me."
    assert layout.reflow(text) == "[D4]Bo: Hello there.[WAIT]\n[D4]Al: Come along\n  with me."


def test_a_break_on_a_speaker_s_indented_line_still_breaks() -> None:
    layout = TextLayout(monospace, 20, speaker=SPEAKER, breaks=WAIT)
    assert layout.reflow("[D4]Bo: one\n  two.[WAIT] Yes.") == "[D4]Bo: one two.[WAIT]\nYes."


def test_each_line_is_measured_once() -> None:
    measured: list[str] = []

    def counting(line: str) -> int:
        measured.append(line)
        return monospace(line)

    TextLayout(counting, 20).reflow("aaaa bbbb cccc dddd eeee ffff gggg hhhh.")
    assert len(measured) == len(set(measured))


def test_an_abbreviation_ends_no_sentence() -> None:
    layout = TextLayout(monospace, 20, abbreviations=("M.",))
    assert layout.reflow("Voici M. Rosa ici. Bon.") == "Voici M. Rosa ici.\nBon."


def test_a_line_never_ends_on_an_abbreviation() -> None:
    layout = TextLayout(monospace, 12, abbreviations=("M.",))
    assert layout.reflow("Bonjour M. Rosa") == "Bonjour\nM. Rosa"


def wide_after_switch(line: str, before: str) -> int:
    """Characters are 1 pixel, 2 once a [wide] switch is in effect (in the line or ahead of it)."""
    return monospace(line) * (2 if "[wide]" in before + line else 1)


def test_a_line_is_measured_in_the_state_ahead_of_it() -> None:
    lines = (
        TextLayout(monospace, 20, measure_after=wide_after_switch).reflow("[wide]aaaa bbbb cccc dddd ee").split("\n")
    )
    assert all(wide_after_switch(line, "\n".join(lines[:index])) <= 20 for index, line in enumerate(lines))


def test_the_measure_after_hook_sees_the_lines_laid_out_ahead() -> None:
    seen: list[tuple[str, str]] = []

    def recording(line: str, before: str) -> int:
        seen.append((line, before))
        return monospace(line)

    TextLayout(monospace, 10, measure_after=recording).reflow("aaaa bbbb. cccc dddd.")
    assert ("cccc dddd.", "aaaa bbbb.") in seen
