"""Pointer formulas: plain arithmetic over values the caller supplies.

They hold no cartridge knowledge. A formula that needs a bus address takes the
ROM-offset-to-bus mapping from the caller (an a816 `Bus`, or the game's own).
"""

import struct
from collections.abc import Callable


def base_relative_16bits_pointer_formula(base: int) -> Callable[[bytes], int]:
    """Read a little-endian 16-bit pointer and add `base`."""
    return lambda v: int(v[0]) + int(v[1] << 8) + base


def long_pointer(base: int, to_bus: Callable[[int], int]) -> Callable[[int], bytes]:
    """Write ROM offset `pointer + base` as a 24-bit little-endian bus address, mapped by `to_bus`."""

    def inner_func(pointer: int) -> bytes:
        bus_address = to_bus(pointer + base)
        return struct.pack("<HB", bus_address & 0xFFFF, bus_address >> 16)

    return inner_func
