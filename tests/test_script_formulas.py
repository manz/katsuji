from dataclasses import dataclass
from typing import Self

from katsuji.script.formulas import base_relative_16bits_pointer_formula, long_pointer


@dataclass(frozen=True)
class LowRom:
    """A LoROM bus address: offsetting crosses into the next bank's ROM window, in the same mirror."""

    logical_value: int

    def __add__(self, offset: int) -> Self:
        bank, window = divmod(self.logical_value, 0x10000)
        linear = bank * 0x8000 + window - 0x8000 + offset
        return type(self)((linear // 0x8000) << 16 | (linear % 0x8000) + 0x8000)


def test_base_relative_pointer_adds_the_base() -> None:
    assert base_relative_16bits_pointer_formula(0x80600)(b"\x34\x12") == 0x80600 + 0x1234


def test_long_pointer_writes_the_offset_bus_address() -> None:
    assert long_pointer(LowRom(0x018000))(0x10) == b"\x10\x80\x01"


def test_long_pointer_stays_in_the_base_mirror() -> None:
    assert long_pointer(LowRom(0xA28000))(0x9000) == b"\x00\x90\xa3"
