"""A small PNG reader and writer on `zlib` and numpy.

Reads 1-, 2-, 4- and 8-bit greyscale, RGB, RGBA and palettized PNGs, with every scanline filter (None, Sub, Up,
Average, Paeth) and CRC-checked chunks. Writes 8-bit greyscale, RGB and RGBA, and palettized PNGs at the smallest
depth (1, 2, 4 or 8) that holds the pixel values. Interlaced and 16-bit PNGs are refused with a clear error; so is
any ancillary chunk other than `PLTE` and `tRNS`, which both decode (ignored on write)."""

import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

Pixels = NDArray[np.uint8]

_SIG = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_PACK_DEPTHS = (1, 2, 4, 8)


def read(path: str | Path) -> tuple[Pixels, tuple[int, ...] | None]:
    """The PNG's pixels and its palette (flat RGB triples) when it is palettized, `None` otherwise. Greyscale pixels
    come back as `(height, width)`; RGB and RGBA as `(height, width, 3 or 4)`; palettized as the colour indices."""
    data = Path(path).read_bytes()
    if data[:8] != _SIG:
        raise ValueError(f"{path}: not a PNG")
    width = height = depth = color_type = 0
    palette: tuple[int, ...] | None = None
    idat = bytearray()
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        if zlib.crc32(ctype + payload) != crc:
            raise ValueError(f"{path}: {ctype.decode('ascii', 'replace')!r} chunk CRC mismatch")
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if interlace:
                raise ValueError(f"{path}: interlaced PNGs are not supported")
            if depth == 16:
                raise ValueError(f"{path}: 16-bit PNGs are not supported")
        elif ctype == b"PLTE":
            palette = tuple(payload)
        elif ctype == b"IDAT":
            idat += payload
        elif ctype == b"IEND":
            break
    channels = _CHANNELS[color_type]
    raw = zlib.decompress(bytes(idat))
    rows = _unfilter(raw, width, height, depth, channels)
    samples = _unpack(rows, depth, width * channels)
    array = samples.reshape(height, width, channels)
    if channels == 1:
        array = array[..., 0]
    return array.copy(), palette if color_type == 3 else None


def write(path: str | Path, pixels: Pixels, palette: tuple[int, ...] | None = None) -> None:
    """Write `pixels` as a PNG. A 2D array with `palette` writes a palettized PNG at the smallest depth that holds
    the palette entries; without one, 8-bit greyscale. A 3D `(h, w, 3 or 4)` array writes 8-bit RGB or RGBA."""
    pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
    if pixels.ndim == 3:
        if palette is not None:
            raise ValueError("palette is not for 3D pixels")
        height, width, channels = pixels.shape
        if channels not in (3, 4):
            raise ValueError(f"3D pixels must have 3 or 4 channels, got {channels}")
        color_type = 2 if channels == 3 else 6
        depth = 8
        samples = pixels.reshape(height, width * channels)
    elif palette is not None:
        height, width = pixels.shape
        color_type = 3
        depth = _min_depth(len(palette) // 3 - 1)
        samples = pixels
    else:
        height, width = pixels.shape
        color_type = 0
        depth = 8
        samples = pixels
    body = _filter_none(_pack(samples, depth))
    ihdr = struct.pack(">IIBBBBB", width, height, depth, color_type, 0, 0, 0)
    chunks = [_chunk(b"IHDR", ihdr)]
    if palette is not None:
        chunks.append(_chunk(b"PLTE", bytes(palette)))
    chunks.append(_chunk(b"IDAT", zlib.compress(body)))
    chunks.append(_chunk(b"IEND", b""))
    Path(path).write_bytes(_SIG + b"".join(chunks))


def _chunk(ctype: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data))


def _min_depth(max_index: int) -> int:
    for depth in _PACK_DEPTHS:
        if max_index < (1 << depth):
            return depth
    raise ValueError(f"palette has more than 256 entries (max index {max_index})")


def _filter_none(packed: NDArray[np.uint8]) -> bytes:
    height, stride = packed.shape
    out = np.zeros((height, stride + 1), dtype=np.uint8)
    out[:, 1:] = packed
    return out.tobytes()


def _pack(samples: NDArray[np.uint8], depth: int) -> NDArray[np.uint8]:
    if depth == 8:
        return samples
    per_byte = 8 // depth
    height, width = samples.shape
    stride = (width + per_byte - 1) // per_byte
    padded = np.zeros((height, stride * per_byte), dtype=np.uint8)
    padded[:, :width] = samples
    packed = np.zeros((height, stride), dtype=np.uint8)
    for i in range(per_byte):
        shift = 8 - depth * (i + 1)
        packed |= padded[:, i::per_byte] << shift
    return packed


def _unfilter(raw: bytes, width: int, height: int, depth: int, channels: int) -> NDArray[np.uint8]:
    bits = channels * depth
    stride = (width * bits + 7) // 8
    fbpp = max(1, bits // 8)
    out = np.zeros((height, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.uint8)
    pos = 0
    for y in range(height):
        f = raw[pos]
        pos += 1
        line = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=pos).copy()
        pos += stride
        if f == 1:
            for i in range(fbpp, stride):
                line[i] = (int(line[i]) + int(line[i - fbpp])) & 0xFF
        elif f == 2:
            line = ((line.astype(np.uint16) + prev.astype(np.uint16)) & 0xFF).astype(np.uint8)
        elif f == 3:
            for i in range(stride):
                left = int(line[i - fbpp]) if i >= fbpp else 0
                line[i] = (int(line[i]) + (left + int(prev[i])) // 2) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = int(line[i - fbpp]) if i >= fbpp else 0
                b = int(prev[i])
                c = int(prev[i - fbpp]) if i >= fbpp else 0
                line[i] = (int(line[i]) + _paeth(a, b, c)) & 0xFF
        elif f != 0:
            raise ValueError(f"unknown PNG filter {f}")
        out[y] = line
        prev = line
    return out


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unpack(rows: NDArray[np.uint8], depth: int, samples_per_row: int) -> NDArray[np.uint8]:
    if depth == 8:
        return rows[:, :samples_per_row]
    mask = (1 << depth) - 1
    per_byte = 8 // depth
    height, stride = rows.shape
    out = np.zeros((height, stride * per_byte), dtype=np.uint8)
    for i in range(per_byte):
        shift = 8 - depth * (i + 1)
        out[:, i::per_byte] = (rows >> shift) & mask
    return out[:, :samples_per_row]
