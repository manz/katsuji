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

# sha256 prefix and length of each game encoder's own output on these inputs (frozen 2026-10-23)
GOLDEN = {
    "text": (("36601b3b0bf2d488", 2520), ("970ca2c81a4fe1cf", 2852)),
    "chain": (("2996aa1c64348fe3", 4423), ("14dacecd9c42aa49", 4178)),
    "far": (("ef62758e7a7190e5", 6075), ("ef62758e7a7190e5", 6075)),
    "runs": (("8c989faf1e714406", 1455), ("f6e5d159910120eb", 607)),
    "tilemap": (("5a904ab5bad0e41e", 1990), ("2293caef72e8baf8", 2113)),
    "random": (("7d3edea1cd9d50d7", 1125), ("7d3edea1cd9d50d7", 1125)),
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
    ],
    ids=["offset-too-wide", "fields-overflow", "fields-overlap", "length-too-long", "window", "window-past-ring"],
)
def test_formats_that_do_not_fit_are_rejected(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="LZSS"):
        replace(STAR_OCEAN, chain=None, **fields)
