"""Typesetting, with bahamut_lagoon's French cases (utils/tests/test_dialog_layout.py) as the spec."""

import pytest

from katsuji.typeset import ENGLISH, FRENCH, Markup, Typography, typeset

BAHAMUT_LAGOON = Markup(
    tag=r"\[character\]\[0x[0-9a-f]+\]|\[[^\]]*\]",
    words=r"\[character\].*",
    glyphs=r"\[0x[0-9a-f]+\]",
    speakers=True,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pour une fois,écoute-moi", "Pour une fois, écoute-moi"),
        ("1,5 lagon", "1,5 lagon"),
        ("Merci,[character][0x0].", "Merci, [character][0x0]."),
        ("Je...je", "Je... je"),
        ("Quoi...?", "Quoi... ?"),
        ("Viens!", "Viens !"),
        ("Viens?!", "Viens ?!"),
        ("    Un  deux", "    Un deux"),
        ("Vint alors la nuit...[end]", "Vint alors la nuit...[end]"),
        ("le seigneur [character][0x0]!", "le seigneur [character][0x0] !"),
        ("Princesse[0xd8]!", "Princesse[0xd8]!"),
        ("Nous vous l'annonçons en ces lieux:", "Nous vous l'annonçons en ces lieux :"),
        ("Roi de Kana: Bonjour.", "Roi de Kana: Bonjour."),
        ("[character][0x1]: Merci.", "[character][0x1]: Merci."),
        ("l'Empereur Sauzer,[end1]", "l'Empereur Sauzer,[end1]"),
    ],
)
def test_french(text: str, expected: str) -> None:
    assert typeset(text, FRENCH, BAHAMUT_LAGOON) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Wait!", "Wait!"),
        ("Who?", "Who?"),
        ("Hi,there", "Hi, there"),
        ("Wait...what", "Wait... what"),
        ("Wait...?", "Wait...?"),
        ('"Run..."', '"Run..."'),
        ("It costs 1,500 gold", "It costs 1,500 gold"),
        ("Hey,[HERO]!", "Hey, [HERO]!"),
        ("Done.[WAIT]", "Done.[WAIT]"),
        ("Well...[WAIT]", "Well...[WAIT]"),
    ],
)
def test_english(text: str, expected: str) -> None:
    assert typeset(text, ENGLISH, Markup(words=r"\[HERO\]")) == expected


def test_a_speaker_colon_gets_its_space_unless_the_game_writes_speakers() -> None:
    assert typeset("Roi de Kana: Bonjour.", FRENCH) == "Roi de Kana : Bonjour."


def test_speaker_space_sets_a_narrow_glyph_before_the_colon() -> None:
    french = Typography(space_before="?!;:", quotes="«»", speaker_space="°")
    assert typeset("Soldat: Bonjour ?", french, Markup(speakers=True)) == "Soldat°: Bonjour ?"


def test_speaker_space_is_idempotent() -> None:
    french = Typography(space_before="?!;:", quotes="«»", speaker_space="°")
    text = "Soldat°: Bonjour ?"
    assert typeset(text, french, Markup(speakers=True)) == text


def test_speaker_space_default_leaves_the_speaker_alone() -> None:
    assert typeset("Soldat: Bonjour.", ENGLISH, Markup(speakers=True)) == "Soldat: Bonjour."


def test_speaker_space_works_through_tags() -> None:
    french = Typography(space_before="?!;:", quotes="«»", speaker_space="°")
    markup = Markup(speakers=True)
    assert typeset("[bold]Soldat[normal]: Bonjour.", french, markup) == "[bold]Soldat[normal]°: Bonjour."


def test_french_quotes_are_spaced_inside() -> None:
    assert typeset("Il dit alors: «Viens!»", FRENCH) == "Il dit alors : « Viens ! »"


def test_a_tag_is_never_spaced_inside() -> None:
    assert typeset("[set,4B]Oui!", FRENCH) == "[set,4B]Oui !"


def test_a_name_reads_as_a_word_after_an_ellipsis() -> None:
    assert typeset("Hm...[HERO]", ENGLISH, Markup(words=r"\[HERO\]")) == "Hm... [HERO]"


def test_each_line_is_typeset_on_its_own() -> None:
    assert typeset("Viens!\nYoyo: oui", FRENCH, BAHAMUT_LAGOON) == "Viens !\nYoyo: oui"


def test_typesetting_twice_changes_nothing() -> None:
    once = typeset("Pour une fois,écoute...moi! «Oui»", FRENCH)
    assert typeset(once, FRENCH) == once


def test_a_private_use_character_is_refused() -> None:
    with pytest.raises(ValueError, match="private-use"):
        typeset("a\ue000b", ENGLISH)


def test_french_glues_its_spaced_marks_and_closing_quote() -> None:
    assert FRENCH.glued == "?!;:»"


def test_english_glues_nothing() -> None:
    assert Typography().glued == ""


@pytest.mark.parametrize(
    "text",
    ["...Heh heh.", "Yes.\n...My heart's", "[WAIT]...dès que", "    ...indented"],
)
def test_an_ellipsis_resuming_a_line_stays_tight(text: str) -> None:
    assert typeset(text, ENGLISH, Markup(words=r"\[HERO\]")) == text


def test_an_ellipsis_after_a_word_still_gets_its_space() -> None:
    assert typeset("Hmm...yes", ENGLISH) == "Hmm... yes"


def test_an_ellipsis_after_a_space_is_spaced_like_one_after_a_word() -> None:
    assert typeset("... ...[0xd8]", FRENCH, BAHAMUT_LAGOON) == "... ... [0xd8]"


def test_squeeze_off_keeps_runs_of_spaces() -> None:
    assert typeset("Nom  Race", FRENCH, squeeze=False) == "Nom  Race"


def test_an_ellipsis_glued_to_a_word_can_stay_glued() -> None:
    stutter = Typography(space_before="?!;:", quotes="«»", space_after_ellipsis=False)
    assert typeset("brouil...lard", stutter) == "brouil...lard"


FRENCH_NEUTRAL = Typography(space_before="?!;:", quotes="«»", neutral_quotes=True)
ENGLISH_CURLY = Typography(quotes="“”", space_inside_quotes=False, neutral_quotes=True)


def test_neutral_quotes_become_french_guillemets_spaced_inside() -> None:
    assert typeset('Il dit "oui" puis "non".', FRENCH_NEUTRAL) == "Il dit « oui » puis « non »."


def test_neutral_quotes_become_english_curly_quotes_tight() -> None:
    assert typeset('He said "yes".', ENGLISH_CURLY) == "He said “yes”."


def test_a_quote_may_span_lines_of_one_text() -> None:
    assert typeset('"Un\ndeux"', FRENCH_NEUTRAL) == "« Un\ndeux »"


def test_a_quote_inside_a_tag_is_not_a_quote() -> None:
    assert typeset('[say "x"]"Oui"', FRENCH_NEUTRAL) == '[say "x"]« Oui »'


def test_an_unpaired_quote_names_the_mark_to_write() -> None:
    with pytest.raises(ValueError, match="open a quote that runs on with '«'"):
        typeset('"Hein ?', FRENCH_NEUTRAL)


def test_a_written_guillemet_runs_on_untouched() -> None:
    """dq6: a quote left open for the next message is written as the mark itself."""
    assert typeset("« Hein ?", FRENCH_NEUTRAL) == "« Hein ?"


def test_neutral_quotes_off_leave_quotes_as_typed() -> None:
    assert typeset('Il dit "oui".', FRENCH) == 'Il dit "oui".'


def test_neutral_quotes_need_a_pair_of_marks() -> None:
    with pytest.raises(ValueError, match="needs an opening and a closing quote"):
        Typography(neutral_quotes=True)
