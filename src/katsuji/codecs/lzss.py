"""LZSS, parameterized: the flag-byte and two-byte-reference family most SNES games ship, one `Lzss` per format.

A flag byte governs the next 8 items, one bit each (`flags_msb_first` picks the order): a `literal` bit is one
byte copied out, the other a reference `b0 b1` to earlier output, `min_match` to `max_match` bytes long. `b0` holds
the offset's low 8 bits; `b1` holds its high bits at `offset_shift` and `length - min_match` at `length_shift`.
The offset is either a backward distance into the output (`ring` None) or a position in a `ring`-byte buffer
filled with `fill`, the first byte written at `ring_start` (Okumura's layout). A reference may overlap the bytes
it writes.

The compressor is greedy: at each position the longest match of at least `min_match` bytes, the nearest one on a
tie, else a literal. `chain` limits the search to that many earlier positions sharing the next `min_match` bytes
(a hash chain, newest first); without it every position in the window is tried, the ring's fill included. Both
choices are part of a format's encoder: two encoders with the same decoder can still differ byte for byte.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Lzss:
    """One LZSS format: the reference layout, the window, and how its encoder searches."""

    window: int
    """Farthest a reference reaches back, in bytes."""
    offset_bits: int = 12
    """Width of the offset: 8 bits in `b0`, the rest in `b1`."""
    offset_shift: int = 0
    """Where the offset's high bits sit in `b1`."""
    length_shift: int = 4
    """Where `length - min_match` sits in `b1`."""
    min_match: int = 3
    max_match: int = 18
    ring: int | None = None
    """A ring buffer of this many bytes: offsets are positions in it, not distances."""
    ring_start: int = 0
    """Where the ring writes the first byte."""
    fill: int = 0
    """What the ring holds before anything is written (and what a distance past the start reads)."""
    literal: int = 1
    """The flag bit marking a literal."""
    flags_msb_first: bool = False
    chain: int | None = None
    """Positions the encoder tries per byte, from a hash chain of the next `min_match` bytes; None tries all."""
    oldest: bool = False
    """The encoder tries lengths longest first and takes the earliest occurrence lying wholly inside the window,
    so a reference never overlaps what it writes (bahamut_lagoon). Distances only."""
    repeats: bool = False
    """With `oldest`: also a repeat of the last `max_match` bytes or fewer, which may overlap. It wins over a
    window match no longer than it, and when the longest prefix is nowhere in the window (bahamut_lagoon's rooms)."""
    pad: int | None = None
    """A literal filling the last flag group to 8 items (bahamut_lagoon: 0xFF); None ends the stream early."""

    def __post_init__(self) -> None:
        high = self.offset_bits - 8
        length_bits = 8 - high
        fields = ((self.offset_shift, high), (self.length_shift, length_bits))
        if not 0 <= high <= 8 or any(shift < 0 or shift + bits > 8 for shift, bits in fields):
            raise ValueError(f"LZSS reference fields do not fit b1: {self}")
        if (((1 << high) - 1) << self.offset_shift) & (((1 << length_bits) - 1) << self.length_shift):
            raise ValueError(f"LZSS offset and length overlap in b1: {self}")
        if self.max_match - self.min_match >= 1 << length_bits:
            raise ValueError(f"LZSS max_match {self.max_match} does not fit {length_bits} length bits")
        if (self.ring or self.window + 1) > 1 << self.offset_bits or (self.ring and self.window > self.ring):
            raise ValueError(f"LZSS window {self.window:#x} does not fit {self.offset_bits} offset bits")
        if (self.oldest and (self.ring or self.chain is not None)) or (self.repeats and not self.oldest):
            raise ValueError(f"LZSS oldest takes distances and no chain, repeats needs oldest: {self}")

    def compress(self, data: bytes) -> bytes:
        """`data` packed by the greedy encoder; `decompress(..., len(data))` gives it back."""
        prefix = bytes([self.fill]) * self.ring if self.ring else b""
        seq = prefix + data
        chains: dict[bytes, list[int]] = {}
        out = bytearray()
        i = 0
        while i < len(data):
            flags_at, flags = len(out), 0
            out.append(0)
            for bit in range(8):
                if i >= len(data):
                    if self.pad is None:
                        break
                    flags |= self.literal << self._bit(bit)
                    out.append(self.pad)
                    continue
                here = len(prefix) + i
                if self.oldest:
                    length, distance = self._oldest(data, i)
                    v = here - distance
                else:
                    length, v = self._longest(seq, data, i, self._candidates(here, chains, data, i))
                step = length if length >= self.min_match else 1
                if step == 1:
                    flags |= self.literal << self._bit(bit)
                    out.append(data[i])
                else:
                    flags |= (1 - self.literal) << self._bit(bit)
                    out += self._reference(self._offset(here, v, len(prefix)), length)
                if self.chain is not None:
                    for p in range(i, i + step):
                        chains.setdefault(data[p : p + self.min_match], []).append(p)
                i += step
            out[flags_at] = flags
        return bytes(out)

    def decompress(self, src: bytes, size: int) -> tuple[bytes, int]:
        """`size` bytes unpacked from `src`, and how many bytes of `src` that read."""
        ring = bytearray([self.fill]) * self.ring if self.ring else bytearray()
        write = self.ring_start
        out = bytearray()
        i = bit = flags = 0
        while len(out) < size:
            if i >= len(src):
                raise ValueError(f"LZSS stream ends after {len(out)} of {size} bytes")
            if bit == 0:
                flags, i = src[i], i + 1
            literal = (flags >> self._bit(bit) & 1) == self.literal
            bit = (bit + 1) % 8
            if literal:
                run = src[i : i + 1]
                i += 1
            else:
                offset, length = self._fields(src[i], src[i + 1])
                i += 2
                run = self._copy(out, ring, offset, write, length)
            for c in run:
                out.append(c)
                if self.ring:
                    ring[write] = c
                    write = (write + 1) % self.ring
        return bytes(out[:size]), i

    def _copy(self, out: bytearray, ring: bytearray, offset: int, write: int, length: int) -> bytes:
        """`length` bytes from `offset`, each read after the previous one landed (an overlapping reference)."""
        if not self.ring:
            run = bytearray()
            for _ in range(length):
                at = len(out) + len(run) - offset
                if offset == 0 or at < 0:
                    run.append(self.fill)  # nothing there yet: what an unwritten buffer holds
                else:
                    run.append(out[at] if at < len(out) else run[at - len(out)])
            return bytes(run)
        scratch = bytearray(ring)
        run = bytearray()
        for k in range(length):
            c = scratch[(offset + k) % self.ring]
            run.append(c)
            scratch[(write + k) % self.ring] = c
        return bytes(run)

    def _bit(self, bit: int) -> int:
        return 7 - bit if self.flags_msb_first else bit

    def _reference(self, offset: int, length: int) -> bytes:
        high = offset >> 8 << self.offset_shift
        return bytes([offset & 0xFF, high | (length - self.min_match) << self.length_shift])

    def _fields(self, b0: int, b1: int) -> tuple[int, int]:
        high_mask = (1 << (self.offset_bits - 8)) - 1
        length_mask = (1 << (16 - self.offset_bits)) - 1
        offset = b0 | (b1 >> self.offset_shift & high_mask) << 8
        return offset, (b1 >> self.length_shift & length_mask) + self.min_match

    def _offset(self, here: int, v: int, prefix: int) -> int:
        """A match at virtual index `v` (the ring's fill, then the data) as the reference's offset."""
        if self.ring:
            return (self.ring_start + v - prefix) % self.ring
        return here - v

    def _candidates(self, here: int, chains: dict[bytes, list[int]], data: bytes, i: int) -> Iterator[int]:
        """Virtual indices a match may start at, nearest first, within the window."""
        if self.chain is None:
            yield from range(here - 1, max(here - self.window, 0) - 1, -1)
            return
        offset = here - i
        for p in reversed(chains.get(data[i : i + self.min_match], [])[-self.chain :]):
            if i - p > self.window:
                return
            yield p + offset

    def _oldest(self, data: bytes, i: int) -> tuple[int, int]:
        """`oldest`'s match for `data[i:]`, (length, distance), or (0, 0): longest first, the earliest occurrence
        wholly inside the window, a repeat of the bytes just before taking over as `repeats` says."""
        window = data[max(i - self.window, 0) : i]
        ahead = data[i : i + self.max_match]
        repeat = _repeat(data[max(i - self.max_match, 0) : i], ahead) if self.repeats else None
        for length in range(len(ahead), self.min_match - 1, -1):
            found = window.find(ahead[:length])
            if found != -1:
                return repeat if repeat and repeat[0] >= length else (length, len(window) - found)
            if repeat and repeat[0] >= self.min_match:
                return repeat
        return 0, 0

    def _longest(self, seq: bytes, data: bytes, i: int, candidates: Iterator[int]) -> tuple[int, int]:
        """The longest match for `data[i:]` among `candidates` (the first found on a tie): (length, index)."""
        limit = min(self.max_match, len(data) - i)
        best_len = best_v = 0
        for v in candidates:
            n = 0
            while n < limit and seq[v + n] == data[i + n]:
                n += 1
            if n > best_len:
                best_len, best_v = n, v
                if n == limit:
                    break
        return best_len, best_v


def _repeat(back: bytes, ahead: bytes) -> tuple[int, int] | None:
    """The longest tail of `back` whose repetition runs past one copy of itself into `ahead`: (length matched,
    its period), or None."""
    for start in range(len(back)):
        pattern = back[start:]
        n = 0
        while n < len(ahead) and pattern[n % len(pattern)] == ahead[n]:
            n += 1
        if n > len(pattern):
            return n, len(pattern)
    return None
