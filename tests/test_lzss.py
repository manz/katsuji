"""Parameterized LZSS: the two games' formats, byte for byte, and round trips."""

import hashlib
import random
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest

from katsuji.codecs.lzss import Lzss

# star_ocean tools/encode_text.py: backward distance, 12-bit offset, length in b1's high nibble, 64-entry chains
STAR_OCEAN = Lzss(window=0xFFF, chain=64)
# dq6 tools/dq6_lzss.py: Okumura ring of 1 KiB from $3BE, 10-bit position, length in b1's low 6 bits, full scan
DQ6 = Lzss(window=0x400, offset_bits=10, offset_shift=6, length_shift=0, max_match=66, ring=0x400, ring_start=0x3BE)
# bahamut_lagoon utils/lz.py: set flag = reference, earliest occurrence longest first, 0xFF padding; rooms add the
# repeat search (lz_compress), graphics leave it out (lz_compress_gfx)
BL_ROOMS = Lzss(window=0xFFF, literal=0, oldest=True, repeats=True, pad=0xFF)
BL_GFX = replace(BL_ROOMS, repeats=False)

# sha256 prefix and length of each game encoder's own output on these inputs (frozen 2026-10-23)
GOLDEN = {
    "text": (("36601b3b0bf2d488", 2520), ("970ca2c81a4fe1cf", 2852)),
    "chain": (("2996aa1c64348fe3", 4423), ("14dacecd9c42aa49", 4178)),
    "far": (("ef62758e7a7190e5", 6075), ("ef62758e7a7190e5", 6075)),
    "runs": (("8c989faf1e714406", 1455), ("f6e5d159910120eb", 607)),
    "tilemap": (("5a904ab5bad0e41e", 1990), ("2293caef72e8baf8", 2113)),
    "random": (("7d3edea1cd9d50d7", 1125), ("7d3edea1cd9d50d7", 1125)),
}

# bahamut_lagoon's lz_compress (rooms) and lz_compress(search_patterns=False) (graphics), frozen 2026-10-24; its 84
# Japanese dialogue rooms (314,461 bytes) re-encoded identically too, checked against the game's encoder
BL_GOLDEN = {
    "text": (("5f9d9271e05de2dc", 2439), ("1adb2e498ebf79d2", 2435)),
    "chain": (("f261ca95b4c6bd1a", 4226), ("f261ca95b4c6bd1a", 4226)),
    "far": (("922f5a243c5e63e9", 6075), ("922f5a243c5e63e9", 6075)),
    "runs": (("a6d281e54c18ac3a", 1458), ("bc93def84053354b", 1469)),
    "tilemap": (("c7ad6bf9848fe322", 1949), ("478ada26a2728019", 1900)),
    "random": (("c7c6c992c1a7abf9", 1125), ("c7c6c992c1a7abf9", 1125)),
}


def cases() -> Iterator[tuple[str, bytes]]:
    """Script text, many equal prefixes (past the 64-entry chain), a repeat past the window, long runs, a
    tilemap, noise."""
    r = random.Random(1)
    words = [b"le ", b"la ", b"des ", b"Ratix", b"Millie", b"\x01\x02", b"\x00\x00", b"...", b" ", b"Dorne"]
    yield "text", b"".join(r.choice(words) for _ in range(3000))
    yield "chain", b"".join(b"abc" + bytes([r.randrange(256)]) for _ in range(2000))
    blob = r.randbytes(200)
    yield "far", blob + r.randbytes(5000) + blob
    yield "runs", b"\xff" * 5000 + bytes(range(256)) * 20
    yield "tilemap", b"".join(bytes([r.choice([0x20, 0x21, 0x40]), r.choice([0x0C, 0x2C])]) for _ in range(27 * 128))
    yield "random", r.randbytes(1000)


CASES = dict(cases())


def digest(packed: bytes) -> tuple[str, int]:
    return hashlib.sha256(packed).hexdigest()[:16], len(packed)


@pytest.mark.parametrize("name", GOLDEN)
def test_star_ocean_format_matches_its_encoder(name: str) -> None:
    assert digest(STAR_OCEAN.compress(CASES[name])) == GOLDEN[name][0]


@pytest.mark.parametrize("name", GOLDEN)
def test_dq6_format_matches_its_encoder(name: str) -> None:
    assert digest(DQ6.compress(CASES[name])) == GOLDEN[name][1]


@pytest.mark.parametrize("name", BL_GOLDEN)
def test_bahamut_lagoon_formats_match_its_encoder(name: str) -> None:
    assert (digest(BL_ROOMS.compress(CASES[name])), digest(BL_GFX.compress(CASES[name]))) == BL_GOLDEN[name]


@pytest.mark.parametrize("lzss", [BL_ROOMS, BL_GFX], ids=["rooms", "gfx"])
@pytest.mark.parametrize("name", BL_GOLDEN)
def test_padded_streams_round_trip(lzss: Lzss, name: str) -> None:
    assert lzss.decompress(lzss.compress(CASES[name]), len(CASES[name]))[0] == CASES[name]


def test_padding_fills_the_last_flag_group() -> None:
    assert BL_GFX.compress(b"ab") == b"\x00ab" + b"\xff" * 6


def test_a_repeat_overlaps_what_it_writes() -> None:
    assert BL_ROOMS.compress(b"ab" * 5)[:5] == b"\x04ab\x02\x50"


@pytest.mark.parametrize("lzss", [STAR_OCEAN, DQ6], ids=["star_ocean", "dq6"])
@pytest.mark.parametrize("name", GOLDEN)
def test_round_trips(lzss: Lzss, name: str) -> None:
    packed = lzss.compress(CASES[name])
    assert lzss.decompress(packed, len(CASES[name])) == (CASES[name], len(packed))


def test_a_ring_reference_reads_the_fill() -> None:
    assert DQ6.compress(b"\0" * 10) == b"\x00\xbd\xc7"  # one reference at $3BD, in the zero fill, 10 long


def test_a_distance_reference_overlaps_what_it_writes() -> None:
    assert STAR_OCEAN.compress(b"abababab") == b"\x03ab\x02\x30"


def test_msb_first_flags_and_zero_literals() -> None:
    lzss = Lzss(window=0xFFF, literal=0, flags_msb_first=True)
    packed = lzss.compress(b"abcabcabc")
    assert (packed[0], lzss.decompress(packed, 9)[0]) == (0b00010000, b"abcabcabc")  # three literals, a reference


def test_a_distance_before_the_start_reads_the_fill() -> None:
    assert Lzss(window=0xFFF, fill=0x20).decompress(b"\x00\x05\x00", 3)[0] == b"   "


def test_a_stream_ending_early_raises() -> None:
    with pytest.raises(ValueError, match="ends after 1 of 4"):
        STAR_OCEAN.decompress(b"\x01a", 4)


@pytest.mark.parametrize(
    "fields",
    [
        {"offset_bits": 17},
        {"offset_shift": 2},
        {"length_shift": 0},
        {"max_match": 19},
        {"window": 0x1000},
        {"ring": 0x400, "window": 0x401, "offset_bits": 10, "offset_shift": 6, "length_shift": 0},
        {"oldest": True, "ring": 0x1000},
        {"repeats": True},
    ],
    ids=[
        "offset-too-wide",
        "fields-overflow",
        "fields-overlap",
        "length-too-long",
        "window",
        "window-past-ring",
        "oldest-with-ring",
        "repeats-without-oldest",
    ],
)
def test_formats_that_do_not_fit_are_rejected(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="LZSS"):
        replace(STAR_OCEAN, chain=None, **fields)


def test_oldest_takes_no_chain() -> None:
    with pytest.raises(ValueError, match="no chain"):
        replace(BL_ROOMS, chain=64)


def test_without_a_size_every_item_is_decoded() -> None:
    packed = BL_GFX.compress(b"abc")
    assert BL_GFX.decompress(packed) == (b"abc" + b"\xff" * 5, len(packed))


def test_a_block_reaches_into_the_history_before_it() -> None:
    first = b"Bahamut Lagoon, "
    block = bytes([0b1, 16, (16 - 3) << 4])  # one reference: 16 bytes from 16 back, in the earlier block
    assert BL_ROOMS.decompress(block, history=first) == (first, 3)


def test_a_ring_takes_the_history() -> None:
    block = bytes([0b0, 0x3BE & 0xFF, 0x3BE >> 8 << 6])  # 3 bytes from where the history was written
    assert DQ6.decompress(block, 3, history=b"xyz") == (b"xyz", 3)


def test_a_cut_reference_raises() -> None:
    with pytest.raises(ValueError, match="cut short"):
        BL_ROOMS.decompress(b"\x01\x10")


def test_a_stream_ending_on_a_flag_byte_stops_there() -> None:
    assert BL_ROOMS.decompress(b"\x00") == (b"", 1)
