"""Pluggable blob storage: local filesystem for the MVP, Azure Blob for production."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageBackend(Protocol):
    name: str

    async def save(self, *, content: bytes, filename: str, content_type: str) -> str:
        """Persist the payload and return a storage URI."""


def build_object_key(filename: str) -> str:
    safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
    return f"{uuid.uuid4()}-{safe_name}"


class LocalStorageBackend:
    name = "local"

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root or settings.LOCAL_STORAGE_PATH)
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(self, *, content: bytes, filename: str, content_type: str) -> str:
        key = build_object_key(filename)
        destination = (self._root / key).resolve()
        if not str(destination).startswith(str(self._root.resolve())):
            raise StorageError("Resolved upload path escapes the storage root.")

        try:
            await asyncio.to_thread(destination.write_bytes, content)
        except OSError as exc:
            raise StorageError("Failed to write the uploaded file to local storage.") from exc

        logger.info("document_stored", extra={"backend": self.name, "key": key})
        return destination.as_uri()


class AzureBlobStorageBackend:
    name = "azure_blob"

    def __init__(self) -> None:
        if not settings.AZURE_STORAGE_CONNECTION_STRING:
            raise StorageError("AZURE_STORAGE_CONNECTION_STRING is not configured.")
        from azure.storage.blob.aio import BlobServiceClient

        self._service = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
        self._container = settings.AZURE_STORAGE_CONTAINER

    async def save(self, *, content: bytes, filename: str, content_type: str) -> str:
        from azure.core.exceptions import AzureError
        from azure.storage.blob import ContentSettings

        key = build_object_key(filename)
        try:
            blob = self._service.get_blob_client(container=self._container, blob=key)
            await blob.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError as exc:
            raise StorageError("Failed to upload the document to Azure Blob Storage.") from exc

        logger.info("document_stored", extra={"backend": self.name, "key": key})
        return f"{self._service.url}{self._container}/{key}"


def get_storage_backend() -> StorageBackend:
    if settings.STORAGE_BACKEND == "azure_blob":
        return AzureBlobStorageBackend()
    return LocalStorageBackend()
