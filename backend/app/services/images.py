"""Profile-photo checks without an image library.

The web client crops and re-encodes photos in the browser (a canvas export carries no camera
metadata) before uploading. The server still trusts nothing: it reads the real format from the
file's own header (never the declared type alone) and its pixel size, and rejects anything else.
Photos are only ever served back to their owner, with nosniff and a sandboxing CSP.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAX_AVATAR_BYTES = 1_000_000
MIN_SIDE = 32
MAX_SIDE = 2048


class InvalidImage(ValueError):
    """Not a PNG, JPEG or WebP we accept; the message is safe to show to the user."""


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    width: int
    height: int


def inspect_image(data: bytes) -> ImageInfo:
    """Format and size from the file header. Raises InvalidImage for anything unsupported."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        info = _png(data)
    elif data.startswith(b"\xff\xd8\xff"):
        info = _jpeg(data)
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        info = _webp(data)
    else:
        raise InvalidImage("Use a PNG, JPEG or WebP image.")
    if not (MIN_SIDE <= info.width <= MAX_SIDE and MIN_SIDE <= info.height <= MAX_SIDE):
        raise InvalidImage(f"The photo must be between {MIN_SIDE} and {MAX_SIDE} pixels on each side.")
    return info


def _png(d: bytes) -> ImageInfo:
    if len(d) < 24 or d[12:16] != b"IHDR":
        raise InvalidImage("This PNG file looks damaged.")
    w, h = struct.unpack(">II", d[16:24])
    return ImageInfo("image/png", w, h)


# Start-of-frame markers carry the size; C4 (huffman), C8 (reserved) and CC (arithmetic) do not.
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg(d: bytes) -> ImageInfo:
    i = 2
    while i + 4 <= len(d):
        if d[i] != 0xFF:
            break
        marker = d[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # no length field
            i += 2
            continue
        (seg_len,) = struct.unpack(">H", d[i + 2 : i + 4])
        if seg_len < 2:
            break
        if marker in _SOF:
            if i + 9 > len(d):
                break
            h, w = struct.unpack(">HH", d[i + 5 : i + 9])
            return ImageInfo("image/jpeg", w, h)
        if marker in (0xD9, 0xDA):  # end of image / start of scan before any frame header
            break
        i += 2 + seg_len
    raise InvalidImage("This JPEG file looks damaged.")


def _webp(d: bytes) -> ImageInfo:
    chunk = d[12:16]
    if chunk == b"VP8 " and len(d) >= 30 and d[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", d[26:30])
        return ImageInfo("image/webp", w & 0x3FFF, h & 0x3FFF)
    if chunk == b"VP8L" and len(d) >= 25 and d[20] == 0x2F:
        b = d[21:25]
        w = 1 + (b[0] | (b[1] & 0x3F) << 8)
        h = 1 + (b[1] >> 6 | b[2] << 2 | (b[3] & 0x0F) << 10)
        return ImageInfo("image/webp", w, h)
    if chunk == b"VP8X" and len(d) >= 30:
        w = 1 + int.from_bytes(d[24:27], "little")
        h = 1 + int.from_bytes(d[27:30], "little")
        return ImageInfo("image/webp", w, h)
    raise InvalidImage("This WebP file looks damaged.")
