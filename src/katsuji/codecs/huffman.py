"""Huffman coding: trees from symbol counts, canonical codes, bit-packed encode and decode.

A game's stream layout stays in the game: where the tree lives and how it is stored (dq6 keeps two child tables
indexed by node offset), where a message starts (a bit offset), what a symbol means. This module gives the parts
around it: `build` a tree, its `codes`, `encode` and `decode` a bit stream, and `nodes` / `from_children` to write
a tree out in preorder or read one back through the game's own tables.

`build` is deterministic: of two subtrees with the same count the one made earlier merges first, the symbols in
the order the counts give them, every merged subtree after them. `canonical` assigns codes from lengths alone, the
DEFLATE way, for a format that stores only the lengths.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Leaf:
    symbol: int


@dataclass(frozen=True)
class Node:
    """An internal node: bit 0 goes to `zero`, bit 1 to `one`."""

    zero: Tree
    one: Tree


type Tree = Leaf | Node
type Child = Leaf | int
"""In a node list: a leaf, or the index of another node."""
type Code = tuple[int, int]
"""A code as (value, bit length), the first bit the value's most significant."""
type _Trie = dict[int, _Trie | Leaf]


def build(counts: Mapping[int, int]) -> Tree:
    """The Huffman tree of `counts` ({symbol: count}); one symbol still gets a 1-bit code."""
    if not counts:
        raise ValueError("Huffman tree of no symbols")
    heap: list[tuple[int, int, Tree]] = [(count, order, Leaf(s)) for order, (s, count) in enumerate(counts.items())]
    heapq.heapify(heap)
    order = len(heap)
    if order == 1:
        return Node(heap[0][2], heap[0][2])
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        heapq.heappush(heap, (a[0] + b[0], order, Node(a[2], b[2])))
        order += 1
    return heap[0][2]


def codes(tree: Tree, strict: bool = False) -> dict[int, Code]:
    """Each symbol's code: its path from the root. A symbol on two leaves keeps the 0 side's, or with `strict`
    raises: a table read from a ROM that holds one twice is corrupt, and encoding it would be ambiguous."""
    found: dict[int, Code] = {}
    stack: list[tuple[Tree, int, int]] = [(tree, 0, 0)]
    while stack:
        node, value, length = stack.pop()
        if isinstance(node, Leaf):
            if strict and node.symbol in found:
                raise ValueError(f"Huffman symbol {node.symbol:#x} is on two leaves")
            found.setdefault(node.symbol, (value, length))
            continue
        stack.append((node.one, value << 1 | 1, length + 1))
        stack.append((node.zero, value << 1, length + 1))
    return found


def canonical(lengths: Mapping[int, int]) -> dict[int, Code]:
    """Codes from bit lengths alone: shorter first, then by symbol, each the previous plus one, shifted left as
    the length grows."""
    out: dict[int, Code] = {}
    value = previous = 0
    for symbol, length in sorted(lengths.items(), key=lambda item: (item[1], item[0])):
        value <<= length - previous
        out[symbol], value, previous = (value, length), value + 1, length
    if previous and value > 1 << previous:
        raise ValueError("Huffman lengths over-subscribe the code space")
    return out


def from_codes(table: Mapping[int, Code]) -> Tree:
    """The tree that decodes `table` (canonical codes, say); codes that are not a complete prefix code raise."""
    root: _Trie = {}
    for symbol, (value, length) in table.items():
        node = root
        for shift in range(length - 1, 0, -1):
            branch = node.setdefault(value >> shift & 1, {})
            if not isinstance(branch, dict):
                raise ValueError(f"Huffman code for {symbol:#x} runs through another's leaf")
            node = branch
        if length < 1 or (value & 1) in node:
            raise ValueError(f"Huffman code for {symbol:#x} collides with another")
        node[value & 1] = Leaf(symbol)
    return _freeze(root)


def _freeze(branch: _Trie) -> Tree:
    if set(branch) != {0, 1}:
        raise ValueError("Huffman codes leave a branch empty")
    zero, one = (half if isinstance(half, Leaf) else _freeze(half) for half in (branch[0], branch[1]))
    return Node(zero, one)


def encode(symbols: Iterable[int], table: Mapping[int, Code], msb_first: bool = True) -> tuple[bytes, int]:
    """`symbols` as a bit stream, and its length in bits; the last byte is padded with zeros."""
    out = bytearray()
    bits = 0
    for symbol in symbols:
        if symbol not in table:
            raise KeyError(f"symbol {symbol:#x} has no Huffman code")
        value, length = table[symbol]
        for shift in range(length - 1, -1, -1):
            if bits % 8 == 0:
                out.append(0)
            if value >> shift & 1:
                out[-1] |= 1 << (7 - bits % 8 if msb_first else bits % 8)
            bits += 1
    return bytes(out), bits


def encode_messages(
    messages: Iterable[Iterable[int]], table: Mapping[int, Code], msb_first: bool = True
) -> tuple[bytes, list[int], int]:
    """`messages` as one bit stream, the bit each one starts at (a pointer table's entries), and the length in
    bits."""
    flat: list[int] = []
    starts: list[int] = []
    bits = 0
    for message in messages:
        starts.append(bits)
        for symbol in message:
            if symbol not in table:
                raise KeyError(f"symbol {symbol:#x} has no Huffman code")
            flat.append(symbol)
            bits += table[symbol][1]
    data, total = encode(flat, table, msb_first)
    return data, starts, total


def decode(data: bytes, tree: Tree, count: int, bit: int = 0, msb_first: bool = True) -> tuple[list[int], int]:
    """`count` symbols read from bit `bit` of `data` on, and the bit after the last."""
    out: list[int] = []
    for _ in range(count):
        node = tree
        while isinstance(node, Node):
            if bit >> 3 >= len(data):
                raise ValueError(f"Huffman stream ends after {len(out)} of {count} symbols")
            mask = 0x80 >> (bit & 7) if msb_first else 1 << (bit & 7)
            node = node.one if data[bit >> 3] & mask else node.zero
            bit += 1
        out.append(node.symbol)
    return out, bit


def nodes(tree: Tree) -> list[tuple[Child, Child]]:
    """The internal nodes in preorder, the root first, each child a leaf or another node's index: the shape a game
    stores its tree in, for the game to lay out as its own tables."""
    if isinstance(tree, Leaf):
        raise ValueError("a lone leaf has no nodes")
    out: list[tuple[Child, Child]] = []

    def place(node: Node) -> int:
        index = len(out)
        out.append((Leaf(-1), Leaf(-1)))  # the slot, filled once the children have theirs
        out[index] = (child(node.zero), child(node.one))
        return index

    def child(node: Tree) -> Child:
        return node if isinstance(node, Leaf) else place(node)

    place(tree)
    return out


def from_children(children: Callable[[int], tuple[Child, Child]], root: int, depth: int = 64) -> Tree:
    """The tree read through `children(index)` (a game's tables, or `nodes(...)`'s list `__getitem__`) from
    `root`; deeper than `depth` raises, as a cyclic table would."""

    def read(index: int, level: int) -> Tree:
        if level > depth:
            raise ValueError(f"Huffman tree deeper than {depth} at node {index:#x}")
        zero, one = children(index)
        return Node(*(c if isinstance(c, Leaf) else read(c, level + 1) for c in (zero, one)))

    return read(root, 0)
