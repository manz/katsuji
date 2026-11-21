"""`katsuji.flow`: how well windows read. A monospace font keeps the widths readable: every character is one
pixel, a tag none."""

import re

from katsuji.dialog import Window
from katsuji.flow import Flaws, Judge, Report, Weights, load
from katsuji.layout import TextLayout
from katsuji.typeset import ENGLISH
from katsuji.windows import Paragraph, windows


def monospace(line: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", "", line))


LAYOUT = TextLayout(monospace, 20, ENGLISH)
JUDGE = Judge(LAYOUT, Window(20, 3))


def test_a_clean_flow_has_no_fault() -> None:
    assert JUDGE.faults([["One.", "Two."]]) == []


def test_an_empty_window_is_a_fault() -> None:
    assert JUDGE.faults([["One."], []]) == ["window 2: empty"]


def test_a_window_of_too_many_lines_is_a_fault() -> None:
    assert JUDGE.faults([["a.", "b.", "c.", "d."]]) == ["window 1: 4 lines, holds 3"]


def test_a_line_wider_than_its_row_is_a_fault() -> None:
    judge = Judge(LAYOUT, Window(20, 2, line_widths={1: 5}))
    assert judge.faults([["One.", "Two two."]]) == ["window 1: 'Two two.' 8 px, row 1 holds 5"]


def test_a_tag_takes_no_width() -> None:
    assert JUDGE.faults([["[red]aaaaaaaaaaaaaaaaaaaa"]]) == []


def test_a_window_is_measured_after_the_windows_ahead() -> None:
    def wide_after_switch(line: str, before: str) -> int:
        return monospace(line) * (2 if "[wide]" in before + line else 1)

    judge = Judge(TextLayout(monospace, 20, ENGLISH, measure_after=wide_after_switch), Window(20, 3))
    assert judge.faults([["[wide]Hi."], ["aaaaaaaaaaaa."]]) == ["window 2: 'aaaaaaaaaaaa.' 26 px, row 0 holds 20"]


def test_each_window_counts() -> None:
    assert JUDGE.flaws([["One."], ["Two."]]).windows == 2


def test_a_window_turned_at_a_sentence_end_carries_nothing() -> None:
    assert JUDGE.flaws([["One two.", "x", "y."], ["Three."]]).carried == 0


def test_a_window_turned_mid_sentence_carries() -> None:
    assert JUDGE.flaws([["One two", "x", "y"], ["three four five."]]).carried == 1


def test_a_closing_quote_still_ends_the_sentence() -> None:
    assert JUDGE.flaws([["He said: « Go. »", "x.", "y."], ["Yes."]]).carried == 0


def test_a_tag_after_the_end_still_ends_the_sentence() -> None:
    assert JUDGE.flaws([["Go![wait]", "x.", "y."], ["Yes."]]).carried == 0


def test_a_turn_carrying_a_word_or_two_dangles() -> None:
    assert JUDGE.flaws([["One two", "x", "y"], ["three."]]).dangles == 1


def test_a_turn_carrying_more_words_does_not_dangle() -> None:
    assert JUDGE.flaws([["One two", "x", "y"], ["three four five."]]).dangles == 0


def test_a_turn_carrying_a_pause_does_not_dangle() -> None:
    assert JUDGE.flaws([["One two", "x", "y"], ["......"]]).dangles == 0


def test_a_dangle_is_counted_as_its_words() -> None:
    judge = Judge(LAYOUT, Window(20, 3), dangle_words=3)
    assert judge.flaws([["One two", "x", "y"], ["three four five."]]).dangles == 1


def test_a_window_of_one_line_another_follows_is_lone() -> None:
    assert JUDGE.flaws([["One."], ["Two."]]).lone == 1


def test_the_last_window_is_never_lone() -> None:
    assert JUDGE.flaws([["One.", "x.", "y."], ["Two."]]).lone == 0


def test_lines_left_empty_before_a_turn_count() -> None:
    assert JUDGE.flaws([["One."], ["Two.", "x."], ["Three."]]).empty == 3


def test_the_last_window_leaves_no_empty_line() -> None:
    assert JUDGE.flaws([["One."]]).empty == 0


def test_a_sentence_broken_onto_a_short_line_tails() -> None:
    assert JUDGE.flaws([["aaaa bbbb cccc dddd", "ee."]]).tails == 1


def test_a_sentence_broken_onto_a_long_line_does_not_tail() -> None:
    assert JUDGE.flaws([["aaaa bbbb cccc dddd", "eeee ffff."]]).tails == 0


def test_a_short_sentence_of_its_own_line_does_not_tail() -> None:
    assert JUDGE.flaws([["Aaaa bbbb cccc.", "Ee."]]).tails == 0


def test_a_tail_is_measured_against_its_row() -> None:
    judge = Judge(LAYOUT, Window(20, 2, line_widths={1: 8}))
    assert judge.flaws([["aaaa bbbb cccc dddd", "ee ff."]]).tails == 0


def test_flaws_add_up() -> None:
    assert Flaws(windows=1, tails=2) + Flaws(windows=3, lone=1) == Flaws(windows=4, lone=1, tails=2)


def test_the_cost_weighs_each_flaw() -> None:
    assert Flaws(windows=2, dangles=1).cost(Weights(windows=10, dangles=5)) == 25


def test_the_cost_weighs_by_default_weights() -> None:
    assert Flaws(windows=1).cost() == Weights().windows


def test_the_judge_costs_by_its_weights() -> None:
    judge = Judge(LAYOUT, Window(20, 3), weights=Weights(windows=1))
    assert judge.cost([["One."], ["Two."]]) == 2 + Weights().lone + 2 * Weights().empty


def test_a_dangle_costs_more_than_a_line_more() -> None:
    """The reason to judge at all: of two flows of the same sentence, the one that turns for one word reads
    worse though it is no longer."""
    dangling = JUDGE.cost([["aaaa bbbb cccc", "dddd eeee ffff", "gggg hhhh"], ["iiii."]])
    balanced = JUDGE.cost([["aaaa bbbb cccc", "dddd eeee ffff"], ["gggg hhhh iiii."]])
    assert balanced < dangling


def test_a_one_tail_flow_costs_a_window_for_no_fewer_tails() -> None:
    """`windows(one_tail=)` turns rather than stack two ragged sentences: the tails stay, a window is added. The
    judge counts tails per sentence, so it prefers the shared window."""
    sentences = ["aaaa bbbb cccc dd.", "eeee ffff gggg hh."]
    judge = Judge(LAYOUT, Window(14, 4), tail=0.6)
    shared = windows(LAYOUT, [Paragraph(sentences)], Window(14, 4))
    alone = windows(LAYOUT, [Paragraph(sentences)], Window(14, 4), one_tail=0.6)
    assert (judge.flaws(shared).tails, judge.flaws(alone).tails, judge.cost(shared) < judge.cost(alone)) == (2, 2, True)


def report(**laid: list[list[str]]) -> Report:
    built = Report(JUDGE)
    for key, windows_ in laid.items():
        built.add(key, windows_)
    return built


def test_a_report_totals_its_messages() -> None:
    assert report(a=[["One."], ["Two."]], b=[["Three."]]).totals().windows == 3


def test_a_report_keeps_the_faults_by_message() -> None:
    assert report(a=[["One."]], b=[["One."], []]).faults == {"b": ["window 2: empty"]}


def test_the_worst_message_comes_first() -> None:
    worst = report(a=[["One two", "x", "y"], ["three."]], b=[["One."], ["Two."]], c=[["Fine."]]).worst()
    assert [key for key, _ in worst] == ["a", "b"]


def test_the_worst_leaves_windows_out() -> None:
    assert report(a=[["One.", "x.", "y."], ["Two."]]).worst() == []


def test_the_worst_keeps_count() -> None:
    assert len(report(a=[["One."], ["Two."]], b=[["One."], ["Two."]]).worst(1)) == 1


def test_a_dump_loads_back() -> None:
    built = report(a=[["One."], ["Two."]])
    assert load(built.dump()) == built.flaws


def test_a_dump_is_a_message_a_line_its_flaws_only() -> None:
    assert report(b=[["One."]], a=[["One."], ["Two."]]).dump() == (
        '{\n"a": {"windows": 2, "lone": 1, "empty": 2},\n"b": {"windows": 1}\n}'
    )


def test_an_empty_report_dumps_empty() -> None:
    assert load(Report(JUDGE).dump()) == {}


def test_nothing_changed_reads_nothing() -> None:
    built = report(a=[["One."], ["Two."]])
    assert built.changes(load(built.dump())) == []


def test_changes_give_the_totals_then_the_messages() -> None:
    before = load(report(a=[["One."], ["Two."]], b=[["Fine."]]).dump())
    after = report(a=[["One.", "Two."]], b=[["Fine."]])
    assert after.changes(before) == ["windows: 3 → 2", "lone: 1 → 0", "empty: 2 → 0", "a: 25 → 10"]


def test_changes_name_a_message_gone_or_new() -> None:
    before = load(report(a=[["One."]]).dump())
    assert report(b=[["One."]]).changes(before) == ["a: 10 → gone", "b: gone → 10"]
