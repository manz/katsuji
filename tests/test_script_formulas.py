from katsuji.script.formulas import base_relative_16bits_pointer_formula, long_pointer


def low_rom(offset: int) -> int:
    return (offset // 0x8000) << 16 | (offset % 0x8000) + 0x8000


def test_base_relative_pointer_adds_the_base() -> None:
    assert base_relative_16bits_pointer_formula(0x80600)(b"\x34\x12") == 0x80600 + 0x1234


def test_long_pointer_maps_through_the_caller() -> None:
    assert long_pointer(0x8000, low_rom)(0x10) == b"\x10\x80\x01"


def test_long_pointer_writes_whatever_the_mapping_returns() -> None:
    assert long_pointer(0, lambda offset: 0xC00000 + offset)(0x123456) == b"\x56\x34\xd2"
