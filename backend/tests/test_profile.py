"""Profile editing and profile photos."""

from __future__ import annotations

import os
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import models as m
from app.services.images import MAX_AVATAR_BYTES, InvalidImage, inspect_image
from tests.conftest import csrf_headers, register

AVATAR = "/api/v1/me/avatar"


# --- tiny real images ----------------------------------------------------------------------------
def png(w: int = 64, h: int = 64, noise: bool = False) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    if noise:  # incompressible, so the file is realistically large
        rows = b"".join(b"\x00" + os.urandom(3 * w) for _ in range(h))
    else:
        rows = b"".join(b"\x00" + b"\x2f\x7b\xff" * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def jpeg_header(w: int, h: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def webp_vp8x(w: int, h: int) -> bytes:
    body = (
        b"VP8X"
        + struct.pack("<I", 10)
        + b"\x00\x00\x00\x00"
        + (w - 1).to_bytes(3, "little")
        + (h - 1).to_bytes(3, "little")
    )
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def webp_vp8l(w: int, h: int) -> bytes:
    bits = (w - 1) | (h - 1) << 14
    body = b"VP8L" + struct.pack("<I", 5) + b"\x2f" + struct.pack("<I", bits)
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def webp_vp8(w: int, h: int) -> bytes:
    frame = b"\x00\x00\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", w, h)
    body = b"VP8 " + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


# --- image inspection ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("data", "kind", "size"),
    [
        (png(64, 48), "image/png", (64, 48)),
        (jpeg_header(512, 384), "image/jpeg", (512, 384)),
        (webp_vp8x(512, 512), "image/webp", (512, 512)),
        (webp_vp8l(300, 200), "image/webp", (300, 200)),
        (webp_vp8(256, 256), "image/webp", (256, 256)),
    ],
)
def test_inspect_reads_format_and_size_from_the_header(data, kind, size):
    info = inspect_image(data)
    assert (info.content_type, (info.width, info.height)) == (kind, size)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"GIF89a" + b"\x00" * 20,
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 4,  # truncated
        b"\xff\xd8\xff\xd9",  # JPEG with no frame header
        b"RIFF\x00\x00\x00\x00WEBPJUNK",
        png(8, 8),  # too small
        png(4000, 40),  # too large
    ],
)
def test_inspect_rejects_other_or_broken_files(data):
    with pytest.raises(InvalidImage):
        inspect_image(data)


# --- name ----------------------------------------------------------------------------------------
def test_edit_display_name(client):
    register(client)
    assert client.patch("/api/v1/me", json={"display_name": "Aziza"}).status_code == 403  # CSRF
    r = client.patch(
        "/api/v1/me", json={"display_name": "  Aziza \n  Karimova "}, headers=csrf_headers(client)
    )
    assert r.status_code == 200 and r.json()["display_name"] == "Aziza Karimova"
    assert client.get("/api/v1/me").json()["user"]["display_name"] == "Aziza Karimova"
    cleared = client.patch("/api/v1/me", json={"display_name": "   "}, headers=csrf_headers(client))
    assert cleared.json()["display_name"] is None


def test_edit_display_name_validation(client):
    register(client)
    h = csrf_headers(client)
    assert client.patch("/api/v1/me", json={"display_name": "x" * 81}, headers=h).status_code == 422
    assert client.patch("/api/v1/me", json={"display_name": "a\u0000b"}, headers=h).status_code == 422
    assert client.patch("/api/v1/me", json={"email": "other@example.com"}, headers=h).status_code == 422


def test_profile_requires_sign_in(client):
    assert client.patch("/api/v1/me", json={"display_name": "x"}).status_code == 401
    assert client.get(AVATAR).status_code == 401
    assert client.put(AVATAR, content=png(), headers={"Content-Type": "image/png"}).status_code == 401


# --- photo ---------------------------------------------------------------------------------------
def upload(client, data: bytes, content_type: str):
    return client.put(AVATAR, content=data, headers={"Content-Type": content_type, **csrf_headers(client)})


def test_upload_view_replace_and_remove_photo(client):
    register(client)
    assert client.get("/api/v1/me").json()["user"]["avatar_url"] is None
    assert client.get(AVATAR).status_code == 404

    first = png()
    r = upload(client, first, "image/png")
    assert r.status_code == 200
    url = r.json()["avatar_url"]
    assert url.startswith(AVATAR + "?v=")
    assert client.get("/api/v1/me").json()["user"]["avatar_url"] == url

    got = client.get(url)
    assert got.status_code == 200 and got.content == first
    assert got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in got.headers["content-security-policy"]
    assert got.headers["cache-control"] == "no-store"  # personal data, like all /api responses

    second = webp_vp8x(512, 512)
    assert upload(client, second, "image/webp").status_code == 200
    assert client.get(AVATAR).content == second

    assert client.delete(AVATAR).status_code == 403  # CSRF
    assert client.delete(AVATAR, headers=csrf_headers(client)).status_code == 204
    assert client.get(AVATAR).status_code == 404
    assert client.get("/api/v1/me").json()["user"]["avatar_url"] is None
    assert client.delete(AVATAR, headers=csrf_headers(client)).status_code == 204  # idempotent


def test_upload_rejects_bad_files(client):
    register(client)
    assert client.put(AVATAR, content=png(), headers={"Content-Type": "image/png"}).status_code == 403  # CSRF
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    assert upload(client, svg, "image/svg+xml").status_code == 422
    assert upload(client, png(), "image/jpeg").status_code == 422  # declared type must match
    assert upload(client, b"", "image/png").status_code == 422
    big = png() + b"\x00" * MAX_AVATAR_BYTES
    r = upload(client, big, "image/png")
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    assert client.get(AVATAR).status_code == 404  # nothing stored


def test_photos_are_private_to_their_owner(client):
    register(client)
    assert upload(client, png(), "image/png").status_code == 200
    with TestClient(client.app) as other:
        register(other, email="someone@example.com")
        assert other.get(AVATAR).status_code == 404  # sees only their own (none)


def test_deleting_the_account_removes_the_photo(client, db_factory):
    register(client)
    assert upload(client, png(), "image/png").status_code == 200
    body = {"password": "correct horse 42"}
    r = client.request("DELETE", "/api/v1/me", json=body, headers=csrf_headers(client))
    assert r.status_code == 204
    with db_factory() as db:
        assert db.scalars(select(m.UserAvatar)).all() == []


def test_realistic_photo_sizes_are_accepted(client):
    """A 512 px photo is far above the 64 KB limit other API requests have."""
    register(client)
    photo = png(512, 400, noise=True)
    assert 64 * 1024 < len(photo) <= MAX_AVATAR_BYTES
    assert upload(client, photo, "image/png").status_code == 200
    assert client.get(AVATAR).content == photo
    # Other endpoints keep the small limit.
    r = client.patch("/api/v1/me", json={"display_name": "x" * 70_000}, headers=csrf_headers(client))
    assert r.status_code == 413
