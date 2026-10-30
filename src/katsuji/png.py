"""A small PNG reader and writer on `zlib` and numpy.

Reads 1-, 2-, 4- and 8-bit greyscale, RGB, RGBA and palettized PNGs, with every scanline filter (None, Sub, Up,
Average, Paeth) and CRC-checked chunks. Writes 8-bit greyscale, RGB and RGBA, and palettized PNGs at the smallest
depth (1, 2, 4 or 8) that holds the pixel values. Interlaced and 16-bit PNGs are refused with a clear error.
`PLTE` and `tRNS` decode; other ancillary chunks are skipped. `read_rgba` applies `tRNS` as `convert("RGBA")` did
in Pillow, and a palettized write carries per-entry alpha as `tRNS`."""

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
    return decode(Path(path).read_bytes())


def decode(data: bytes) -> tuple[Pixels, tuple[int, ...] | None]:
    """`read` for a PNG held in memory: same return shape, same constraints."""
    pixels, palette, _, color_type, _ = _decode(data)
    return pixels, palette if color_type == 3 else None


def read_rgba(path: str | Path) -> Pixels:
    """The PNG as `(height, width, 4)` RGBA whatever its colour type: palette entries and greys expand to RGB (1-,
    2- and 4-bit greys scale to 0-255, where `read` keeps the samples), and
    `tRNS` gives the alpha (per palette entry, or the one transparent grey or RGB colour); otherwise opaque."""
    return decode_rgba(Path(path).read_bytes())


def decode_rgba(data: bytes) -> Pixels:
    """`read_rgba` for a PNG held in memory."""
    pixels, palette, trns, color_type, depth = _decode(data)
    if color_type == 3:
        return _expand_palette(pixels, palette or (), trns)
    if color_type == 4:
        return pixels[..., [0, 0, 0, 1]].copy()
    if color_type == 6:
        return pixels
    if color_type == 0:
        rgb = np.repeat((pixels * (255 // ((1 << depth) - 1)))[..., None], 3, axis=2).astype(np.uint8)
    else:
        rgb = pixels
    alpha = np.full(pixels.shape[:2], 255, np.uint8)
    if trns is not None:
        alpha[_color_key_mask(pixels, trns, color_type)] = 0
    return np.dstack([rgb, alpha])


def _expand_palette(indices: Pixels, palette: tuple[int, ...], trns: bytes | None) -> Pixels:
    entries = len(palette) // 3
    alpha = np.full(entries, 255, np.uint8)
    if trns is not None:
        alpha[: len(trns)] = np.frombuffer(trns[:entries], dtype=np.uint8)
    table = np.column_stack([np.asarray(palette, dtype=np.uint8).reshape(-1, 3), alpha])
    if indices.size and int(indices.max()) >= entries:
        raise ValueError(f"pixel index {int(indices.max())} past the {entries}-entry palette")
    return table[indices]


def _color_key_mask(pixels: Pixels, trns: bytes, color_type: int) -> NDArray[np.bool_]:
    """Where the pixels are the one colour `tRNS` makes transparent (16-bit samples; 8-bit PNGs use the low byte)."""
    key = [value & 0xFF for value in struct.unpack(f">{len(trns) // 2}H", trns)]
    if color_type == 0:
        return np.asarray(pixels == key[0])
    return np.asarray(np.all(pixels == np.asarray(key[:3], dtype=np.uint8), axis=2))


def _decode(data: bytes) -> tuple[Pixels, tuple[int, ...] | None, bytes | None, int, int]:
    """Pixels, `PLTE` palette, raw `tRNS` payload, colour type and bit depth."""
    if data[:8] != _SIG:
        raise ValueError("not a PNG")
    width = height = depth = color_type = 0
    palette: tuple[int, ...] | None = None
    trns: bytes | None = None
    idat = bytearray()
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        if zlib.crc32(ctype + payload) != crc:
            raise ValueError(f"{ctype.decode('ascii', 'replace')!r} chunk CRC mismatch")
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if interlace:
                raise ValueError("interlaced PNGs are not supported")
            if depth == 16:
                raise ValueError("16-bit PNGs are not supported")
        elif ctype == b"PLTE":
            palette = tuple(payload)
        elif ctype == b"tRNS":
            trns = bytes(payload)
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
    return array.copy(), palette, trns, color_type, depth


def write(
    path: str | Path,
    pixels: Pixels,
    palette: tuple[int, ...] | None = None,
    alpha: tuple[int, ...] | None = None,
) -> None:
    """Write `pixels` as a PNG. A 2D array with `palette` writes a palettized PNG at the smallest depth that holds
    the palette entries, with `alpha` (one value per entry) as its `tRNS`; without a palette, 8-bit greyscale. A 3D
    `(h, w, 3 or 4)` array writes 8-bit RGB or RGBA."""
    Path(path).write_bytes(encode(pixels, palette, alpha))


def encode(pixels: Pixels, palette: tuple[int, ...] | None = None, alpha: tuple[int, ...] | None = None) -> bytes:
    """`write` to memory: the PNG's raw bytes, for streaming or writing into a buffer."""
    pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
    if alpha is not None and palette is None:
        raise ValueError("alpha is per palette entry: it needs a palette")
    if alpha is not None and palette is not None and len(alpha) > len(palette) // 3:
        raise ValueError(f"{len(alpha)} alpha values for a {len(palette) // 3}-entry palette")
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
    if alpha is not None:
        chunks.append(_chunk(b"tRNS", bytes(_trimmed(alpha))))
    chunks.append(_chunk(b"IDAT", zlib.compress(body)))
    chunks.append(_chunk(b"IEND", b""))
    return _SIG + b"".join(chunks)


def _trimmed(alpha: tuple[int, ...]) -> tuple[int, ...]:
    """`alpha` without its trailing opaque entries, which `tRNS` leaves implied."""
    end = len(alpha)
    while end and alpha[end - 1] == 255:
        end -= 1
    return alpha[:end]


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
