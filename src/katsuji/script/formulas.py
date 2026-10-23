"""Pointer formulas: plain arithmetic over values the caller supplies.

They hold no cartridge knowledge. A formula that needs a bus address takes one
from the caller, in the mirror the caller chose (an a816 `Address`).
"""

import struct
from collections.abc import Callable
from typing import Protocol, Self


class BusAddress(Protocol):
    """A bus address that stays in its own mirror when offset: an a816 `Address` fits."""

    @property
    def logical_value(self) -> int: ...

    def __add__(self, offset: int, /) -> Self: ...


def base_relative_16bits_pointer_formula(base: int) -> Callable[[bytes], int]:
    """Read a little-endian 16-bit pointer and add `base`."""
    return lambda v: int(v[0]) + int(v[1] << 8) + base


def long_pointer(base: BusAddress) -> Callable[[int], bytes]:
    """Write `base + pointer` as a 24-bit little-endian bus address, in `base`'s mirror."""

    def inner_func(pointer: int) -> bytes:
        bus_address = (base + pointer).logical_value
        return struct.pack("<HB", bus_address & 0xFFFF, bus_address >> 16)

    return inner_func
