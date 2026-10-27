"""`katsuji.png` round-trips every colour type and bit depth, and reads back what Pillow writes."""

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
    import struct
    import zlib

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
