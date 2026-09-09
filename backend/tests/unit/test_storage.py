"""Unit tests for local storage and document text extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import StorageError
from app.services.storage import LocalStorageBackend, build_object_key
from app.utils.text_extraction import extract_text


async def test_local_backend_writes_file_and_returns_uri(tmp_path: Path) -> None:
    backend = LocalStorageBackend(tmp_path)
    uri = await backend.save(content=b"hello", filename="sop.txt", content_type="text/plain")

    assert uri.startswith("file:")
    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert written[0].read_bytes() == b"hello"


async def test_object_key_strips_path_traversal() -> None:
    key = build_object_key("../../etc/passwd")
    assert "/" not in key
    assert "\\" not in key
    assert key.endswith("passwd")


async def test_local_backend_rejects_escaping_paths(tmp_path: Path, monkeypatch) -> None:
    backend = LocalStorageBackend(tmp_path)
    monkeypatch.setattr(
        "app.services.storage.build_object_key", lambda filename: "../escaped.txt"
    )
    with pytest.raises(StorageError):
        await backend.save(content=b"x", filename="a.txt", content_type="text/plain")


def test_extract_text_reads_plain_text() -> None:
    assert extract_text(b"Step one\nStep two", "sop.txt", "text/plain") == "Step one\nStep two"


def test_extract_text_returns_none_for_unsupported_type() -> None:
    assert extract_text(b"\x00\x01", "image.png", "image/png") is None


def test_extract_text_survives_corrupt_pdf() -> None:
    assert extract_text(b"not-a-real-pdf", "broken.pdf", "application/pdf") is None
