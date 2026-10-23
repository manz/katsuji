"""Huffman: trees, codes, bit streams, and dq6's twin-table layout written from `nodes`."""

import hashlib
import random

import pytest

from katsuji.codecs import huffman
from katsuji.codecs.huffman import Leaf, Node


def dq6_tables(tree: huffman.Tree) -> bytes:
    """dq6's layout (tools/dq6_huffman.py): two 16-bit child tables by node byte offset, a node child as
    `offset | 0x8000`, a leaf as its symbol; the root at offset 0."""
    zeros, ones = bytearray(), bytearray()
    for zero, one in huffman.nodes(tree):
        for table, child in ((zeros, zero), (ones, one)):
            entry = child.symbol if isinstance(child, Leaf) else child * 2 | 0x8000
            table += entry.to_bytes(2, "little")
    return bytes(zeros + ones)


def counts(name: str) -> dict[int, int]:
    r = random.Random(6)
    if name == "zipf":
        return {s: 10000 // (i + 1) for i, s in enumerate(r.sample(range(0x800), 600))}
    if name == "ties":
        r.sample(range(0x800), 600)
        return {s: r.choice([1, 2, 3, 5]) for s in range(300)}
    return {s: 7 for s in range(64)} if name == "flat" else {0x20: 3, 0x41: 1}


# sha256 prefix of dq6's build_tree tables on the same counts (frozen 2026-10-23)
DQ6_TABLES = {
    "zipf": "f8f3a932f861cbe3",
    "ties": "4dbac53b5e98499e",
    "flat": "e5ad75254cf5f87d",
    "two": "9a5bca26c18598bc",
}


@pytest.mark.parametrize("name", DQ6_TABLES)
def test_build_lays_out_as_dq6s_tree(name: str) -> None:
    assert hashlib.sha256(dq6_tables(huffman.build(counts(name)))).hexdigest()[:16] == DQ6_TABLES[name]


def test_equal_counts_merge_in_the_order_given() -> None:
    assert huffman.build({1: 1, 2: 1, 3: 1}) == Node(Leaf(3), Node(Leaf(1), Leaf(2)))


def test_one_symbol_gets_a_one_bit_code() -> None:
    assert huffman.codes(huffman.build({7: 4})) == {7: (0, 1)}


def test_no_symbols_raise() -> None:
    with pytest.raises(ValueError, match="no symbols"):
        huffman.build({})


def test_frequent_symbols_get_shorter_codes() -> None:
    table = huffman.codes(huffman.build({0: 50, 1: 20, 2: 20, 3: 10}))
    assert [table[s][1] for s in range(4)] == [1, 3, 2, 3]  # 1 and 2 tie: 1 (given first) merges first


@pytest.mark.parametrize("msb_first", [True, False])
def test_encode_and_decode_round_trip(msb_first: bool) -> None:
    tree = huffman.build(counts("zipf"))
    message = random.Random(2).choices(list(counts("zipf")), k=500)
    packed, bits = huffman.encode(message, huffman.codes(tree), msb_first)
    assert huffman.decode(packed, tree, len(message), msb_first=msb_first) == (message, bits)


def test_decode_starts_at_a_bit_offset() -> None:
    tree = huffman.build({0: 3, 1: 1})  # 0 -> "1", 1 -> "0"
    assert huffman.decode(b"\x0b", tree, 4, bit=4) == ([0, 1, 0, 0], 8)  # bits 1011 after the first nibble


def test_canonical_codes_follow_lengths_then_symbols() -> None:
    assert huffman.canonical({ord("a"): 2, ord("b"): 1, ord("c"): 3, ord("d"): 3}) == {
        ord("b"): (0b0, 1),
        ord("a"): (0b10, 2),
        ord("c"): (0b110, 3),
        ord("d"): (0b111, 3),
    }


def test_canonical_codes_decode_through_from_codes() -> None:
    table = huffman.canonical({s: n for s, (_, n) in huffman.codes(huffman.build(counts("ties"))).items()})
    message = list(range(300))
    packed, _ = huffman.encode(message, table)
    assert huffman.decode(packed, huffman.from_codes(table), 300)[0] == message


def test_over_subscribed_lengths_raise() -> None:
    with pytest.raises(ValueError, match="over-subscribe"):
        huffman.canonical({1: 1, 2: 1, 3: 1})


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ({1: (0, 1), 2: (0b01, 2), 3: (1, 1)}, "runs through"),
        ({1: (0, 1), 2: (0, 1)}, "collides"),
        ({1: (0, 1)}, "branch empty"),
    ],
    ids=["prefix", "duplicate", "incomplete"],
)
def test_from_codes_rejects_codes_that_are_no_prefix_code(table: dict[int, huffman.Code], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        huffman.from_codes(table)


def test_nodes_read_back_through_from_children() -> None:
    tree = huffman.build(counts("zipf"))
    assert huffman.from_children(huffman.nodes(tree).__getitem__, 0) == tree


def test_nodes_of_a_lone_leaf_raise() -> None:
    with pytest.raises(ValueError, match="lone leaf"):
        huffman.nodes(Leaf(1))


def test_a_cyclic_table_raises() -> None:
    with pytest.raises(ValueError, match="deeper than 64"):
        huffman.from_children(lambda index: (index, Leaf(0)), 0)


def test_an_unknown_symbol_raises() -> None:
    with pytest.raises(KeyError, match="0x9"):
        huffman.encode([9], {1: (0, 1)})


def test_a_stream_ending_early_raises() -> None:
    with pytest.raises(ValueError, match="ends after 8 of 9"):
        huffman.decode(b"\x00", huffman.build({0: 3, 1: 1}), 9)
