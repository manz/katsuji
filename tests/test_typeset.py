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
