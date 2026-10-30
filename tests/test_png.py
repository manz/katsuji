"""`katsuji.png` round-trips every colour type and bit depth, and reads back what Pillow writes."""

import struct
import zlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from katsuji import png

LEVELS_1 = np.array([0, 255], dtype=np.uint8)
LEVELS_2 = np.array([0, 85, 170, 255], dtype=np.uint8)
LEVELS_4 = np.array([i * 17 for i in range(16)], dtype=np.uint8)


def test_read_rejects_a_non_png(tmp_path: Path) -> None:
    (tmp_path / "f.png").write_bytes(b"NOT A PNG" + b"\x00" * 100)
    with pytest.raises(ValueError, match="not a PNG"):
        png.read(tmp_path / "f.png")


def _retouch_ihdr(path: Path, offset: int, value: int) -> None:
    """Rewrite one byte in the IHDR payload and fix its CRC (offset 0 is the first byte of the payload)."""
    data = bytearray(path.read_bytes())
    ihdr_start = 8 + 8  # signature + length(4) + type(4)
    data[ihdr_start + offset] = value
    crc = zlib.crc32(data[ihdr_start - 4 : ihdr_start + 13])
    data[ihdr_start + 13 : ihdr_start + 17] = struct.pack(">I", crc)
    path.write_bytes(bytes(data))


def test_read_rejects_interlaced(tmp_path: Path) -> None:
    Image.fromarray(np.zeros((4, 4), dtype=np.uint8), mode="L").save(tmp_path / "f.png")
    _retouch_ihdr(tmp_path / "f.png", offset=12, value=1)  # interlace byte
    with pytest.raises(ValueError, match="interlaced"):
        png.read(tmp_path / "f.png")


def test_read_rejects_16_bit(tmp_path: Path) -> None:
    Image.fromarray(np.zeros((4, 4), dtype=np.uint8), mode="L").save(tmp_path / "f.png")
    _retouch_ihdr(tmp_path / "f.png", offset=8, value=16)  # bit depth byte
    with pytest.raises(ValueError, match="16-bit"):
        png.read(tmp_path / "f.png")


def test_read_flags_a_crc_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "f.png"
    Image.fromarray(np.zeros((2, 2), dtype=np.uint8), mode="L").save(path)
    data = bytearray(path.read_bytes())
    data[-5] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="CRC"):
        png.read(path)


def test_8_bit_grey_round_trips(tmp_path: Path) -> None:
    pixels = np.arange(64, dtype=np.uint8).reshape(8, 8)
    png.write(tmp_path / "f.png", pixels)
    out, palette = png.read(tmp_path / "f.png")
    assert palette is None
    assert out.tolist() == pixels.tolist()


def test_rgb_round_trips(tmp_path: Path) -> None:
    pixels = np.zeros((2, 3, 3), dtype=np.uint8)
    pixels[0, 1] = (255, 128, 0)
    pixels[1, 2] = (0, 64, 200)
    png.write(tmp_path / "f.png", pixels)
    out, palette = png.read(tmp_path / "f.png")
    assert palette is None
    assert out.tolist() == pixels.tolist()


def test_rgba_round_trips(tmp_path: Path) -> None:
    pixels = np.zeros((2, 2, 4), dtype=np.uint8)
    pixels[0, 0] = (255, 0, 0, 128)
    pixels[1, 1] = (0, 255, 0, 255)
    png.write(tmp_path / "f.png", pixels)
    out, _ = png.read(tmp_path / "f.png")
    assert out.tolist() == pixels.tolist()


@pytest.mark.parametrize("entries", [2, 4, 16, 256])
def test_palette_round_trips_at_the_smallest_depth(tmp_path: Path, entries: int) -> None:
    palette = tuple(c for i in range(entries) for c in (i, i, i))
    width = min(32, entries * 2)
    pixels = np.tile(np.arange(entries, dtype=np.uint8), (4, width // entries))
    png.write(tmp_path / "f.png", pixels, palette=palette)
    out, out_palette = png.read(tmp_path / "f.png")
    assert out_palette == palette
    assert out.tolist() == pixels.tolist()


def test_palette_write_picks_the_depth_from_the_palette_size(tmp_path: Path) -> None:
    pixels = np.zeros((2, 2), dtype=np.uint8)
    png.write(tmp_path / "f.png", pixels, palette=(0, 0, 0, 255, 255, 255))
    assert png.read(tmp_path / "f.png")[0].max() < 2
    data = (tmp_path / "f.png").read_bytes()
    assert data[8 + 4 + 4 + 8] == 1  # IHDR bit depth


@pytest.mark.parametrize(("depth", "levels"), [(1, LEVELS_1), (2, LEVELS_2), (4, LEVELS_4)])
def test_reads_pillow_s_low_bit_depth_grey(tmp_path: Path, depth: int, levels: np.ndarray) -> None:
    indices = np.arange(levels.size, dtype=np.uint8).reshape(1, -1)
    greys = levels[indices]
    image = Image.fromarray(greys, mode="L")
    image.save(tmp_path / "f.png", bits=depth)
    out, _ = png.read(tmp_path / "f.png")
    assert out[0].tolist() == greys[0].tolist()


@pytest.mark.parametrize("depth", [1, 2, 4, 8])
def test_reads_pillow_s_palettized_pngs(tmp_path: Path, depth: int) -> None:
    entries = 1 << depth
    pixels = np.tile(np.arange(entries, dtype=np.uint8), (2, 1))
    image = Image.fromarray(pixels, mode="P")
    image.putpalette([v for i in range(entries) for v in (i, 255 - i, 0)])
    image.save(tmp_path / "f.png", bits=depth)
    out, palette = png.read(tmp_path / "f.png")
    assert palette is not None and len(palette) >= entries * 3
    assert out.tolist() == pixels.tolist()


@pytest.mark.parametrize("mode", ["L", "RGB", "RGBA"])
def test_reads_pillow_s_filtered_scanlines(tmp_path: Path, mode: str) -> None:
    rng = np.random.default_rng(0)
    channels = {"L": 1, "RGB": 3, "RGBA": 4}[mode]
    shape = (8, 8) if channels == 1 else (8, 8, channels)
    pixels = rng.integers(0, 256, size=shape, dtype=np.uint8)
    Image.fromarray(pixels, mode=mode).save(tmp_path / "f.png")
    out, _ = png.read(tmp_path / "f.png")
    assert out.tolist() == pixels.tolist()


def test_a_two_colour_palette_is_rejected_for_3d_pixels(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not for 3D"):
        png.write(tmp_path / "f.png", np.zeros((2, 2, 3), dtype=np.uint8), palette=(0, 0, 0, 255, 255, 255))


def test_encode_round_trips_through_decode() -> None:
    pixels = np.arange(16, dtype=np.uint8).reshape(4, 4)
    out, palette = png.decode(png.encode(pixels))
    assert palette is None
    assert out.tolist() == pixels.tolist()


def test_encode_matches_write(tmp_path: Path) -> None:
    pixels = np.array([[0, 1], [1, 0]], dtype=np.uint8)
    png.write(tmp_path / "f.png", pixels, palette=(255, 255, 255, 0, 0, 0))
    assert png.encode(pixels, palette=(255, 255, 255, 0, 0, 0)) == (tmp_path / "f.png").read_bytes()


def test_decode_matches_read(tmp_path: Path) -> None:
    pixels = np.zeros((3, 3, 3), dtype=np.uint8)
    pixels[1, 1] = (255, 128, 0)
    png.write(tmp_path / "f.png", pixels)
    disk, _ = png.read(tmp_path / "f.png")
    memory, _ = png.decode((tmp_path / "f.png").read_bytes())
    assert disk.tolist() == memory.tolist()


def _with_chunk_before_idat(data: bytes, ctype: bytes, payload: bytes) -> bytes:
    """`data` with one more chunk spliced in ahead of its first `IDAT`."""
    at = data.index(b"IDAT") - 4
    return data[:at] + png._chunk(ctype, payload) + data[at:]


def test_palette_alpha_round_trips_through_trns() -> None:
    pixels = np.array([[0, 1], [2, 1]], dtype=np.uint8)
    data = png.encode(pixels, palette=(0, 0, 0, 255, 0, 0, 0, 255, 0), alpha=(0, 128))
    rgba = png.decode_rgba(data)
    assert rgba[..., 3].tolist() == [[0, 128], [255, 128]]


def test_palette_alpha_keeps_the_rgb_entries() -> None:
    pixels = np.array([[0, 1]], dtype=np.uint8)
    data = png.encode(pixels, palette=(1, 2, 3, 4, 5, 6), alpha=(0,))
    assert png.decode_rgba(data)[0].tolist() == [[1, 2, 3, 0], [4, 5, 6, 255]]


def test_decode_keeps_its_return_shape_with_trns() -> None:
    pixels = np.array([[0, 1]], dtype=np.uint8)
    out, palette = png.decode(png.encode(pixels, palette=(1, 2, 3, 4, 5, 6), alpha=(0,)))
    assert (out.tolist(), palette) == ([[0, 1]], (1, 2, 3, 4, 5, 6))


def test_opaque_trailing_alpha_is_left_out_of_trns() -> None:
    data = png.encode(np.zeros((1, 1), np.uint8), palette=(0, 0, 0, 1, 1, 1), alpha=(0, 255))
    at = data.index(b"tRNS")
    assert data[at - 4 : at] == b"\x00\x00\x00\x01"


def test_all_opaque_alpha_matches_no_alpha() -> None:
    pixels = np.array([[0, 1]], dtype=np.uint8)
    palette = (0, 0, 0, 1, 1, 1)
    assert png.encode(pixels, palette, alpha=(255, 255))[-12:] == png.encode(pixels, palette)[-12:]


def test_a_palette_without_trns_reads_opaque() -> None:
    data = png.encode(np.array([[0, 1]], dtype=np.uint8), palette=(0, 0, 0, 1, 1, 1))
    assert png.decode_rgba(data)[..., 3].tolist() == [[255, 255]]


def test_alpha_needs_a_palette() -> None:
    with pytest.raises(ValueError, match="needs a palette"):
        png.encode(np.zeros((1, 1), np.uint8), alpha=(0,))


def test_alpha_longer_than_the_palette_is_refused() -> None:
    with pytest.raises(ValueError, match="2 alpha values for a 1-entry palette"):
        png.encode(np.zeros((1, 1), np.uint8), palette=(0, 0, 0), alpha=(0, 0))


def test_an_index_past_the_palette_is_refused() -> None:
    data = png.encode(np.array([[0, 3]], dtype=np.uint8), palette=(0,) * 12)
    short = data.replace(png._chunk(b"PLTE", bytes(12)), png._chunk(b"PLTE", bytes(6)))
    with pytest.raises(ValueError, match="past the 2-entry palette"):
        png.decode_rgba(short)


def test_grey_trns_makes_its_one_grey_transparent() -> None:
    data = _with_chunk_before_idat(png.encode(np.array([[7, 9]], dtype=np.uint8)), b"tRNS", b"\x00\x07")
    assert png.decode_rgba(data)[0].tolist() == [[7, 7, 7, 0], [9, 9, 9, 255]]


def test_rgb_trns_makes_its_one_colour_transparent() -> None:
    pixels = np.array([[[1, 2, 3], [1, 2, 4]]], dtype=np.uint8)
    data = _with_chunk_before_idat(png.encode(pixels), b"tRNS", b"\x00\x01\x00\x02\x00\x03")
    assert png.decode_rgba(data)[0, :, 3].tolist() == [0, 255]


def test_rgba_reads_as_is() -> None:
    pixels = np.arange(8, dtype=np.uint8).reshape(1, 2, 4)
    assert np.array_equal(png.decode_rgba(png.encode(pixels)), pixels)


def test_grey_alpha_expands_to_rgba(tmp_path: Path) -> None:
    Image.fromarray(np.array([[[5, 6]]], dtype=np.uint8), "LA").save(tmp_path / "la.png")
    assert png.read_rgba(tmp_path / "la.png")[0, 0].tolist() == [5, 5, 5, 6]


def test_read_rgba_matches_pillow_on_a_palette_with_trns(tmp_path: Path) -> None:
    image = Image.fromarray(np.array([[0, 1, 2]], dtype=np.uint8), "P")
    image.putpalette([10, 20, 30, 40, 50, 60, 70, 80, 90])
    image.info["transparency"] = bytes([0, 99])
    image.save(tmp_path / "p.png", transparency=bytes([0, 99]))
    expected = np.asarray(Image.open(tmp_path / "p.png").convert("RGBA"))
    assert np.array_equal(png.read_rgba(tmp_path / "p.png"), expected)


def test_write_carries_alpha(tmp_path: Path) -> None:
    png.write(tmp_path / "f.png", np.array([[0]], dtype=np.uint8), palette=(1, 2, 3), alpha=(4,))
    assert png.read_rgba(tmp_path / "f.png")[0, 0].tolist() == [1, 2, 3, 4]


@pytest.mark.parametrize("depth", [1, 2, 4])
def test_read_rgba_scales_low_bit_depth_grey(depth: int) -> None:
    top = (1 << depth) - 1
    body = png._filter_none(png._pack(np.array([[0, top]], dtype=np.uint8), depth))
    ihdr = png._chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, depth, 0, 0, 0, 0))
    data = png._SIG + ihdr + png._chunk(b"IDAT", zlib.compress(body)) + png._chunk(b"IEND", b"")
    assert png.decode_rgba(data)[0, :, 0].tolist() == [0, 255]
