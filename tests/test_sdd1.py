"""S-DD1 codec: the compressor round-trips through the decoder, under every header."""

import random

import pytest

from katsuji.codecs import sdd1


@pytest.mark.parametrize(
    "data",
    [b"\0", b"\xff" * 33, bytes(range(256)) * 4, random.Random(7).randbytes(777), b"\x55\xaa" * 300],
    ids=["zero", "ones-odd", "ramp", "random", "pattern"],
)
def test_round_trips(data: bytes) -> None:
    assert sdd1.decompress_bytes(sdd1.compress(data), len(data))[0] == data


@pytest.mark.parametrize("header", sdd1.HEADERS, ids=lambda h: f"{h:02X}")
def test_every_header_round_trips(header: int) -> None:
    data = random.Random(header).randbytes(300)
    packed = sdd1.encode(data, header)
    assert (packed[0] & 0xF0, sdd1.decompress_bytes(packed, len(data))[0]) == (header, data)


def test_decoder_reports_the_bytes_it_read() -> None:
    packed = sdd1.compress(bytes(range(256)))
    assert sdd1.decompress_bytes(packed + b"\xaa" * 8, 256)[1] == len(packed)


def test_compress_keeps_the_shortest_header() -> None:
    data = b"\x55\xaa" * 300
    assert len(sdd1.compress(data)) == min(len(sdd1.encode(data, header)) for header in sdd1.HEADERS)


def test_encode_rejects_a_header_outside_headers() -> None:
    with pytest.raises(ValueError, match="0x11"):
        sdd1.encode(b"\0", 0x11)
