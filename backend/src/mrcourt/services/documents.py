"""Case document storage on local disk (swap `save` for object storage in production)."""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from mrcourt.config import get_settings

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


class UnsafeUpload(Exception):
    """Raised by a scanner to reject a file."""


def scan_none(data: bytes) -> None:
    """Default scanner: accepts everything. Replace SCANNER with an antivirus check in production."""


SCANNER = scan_none

_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/msword": (b"\xd0\xcf\x11\xe0",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
}


def content_matches_type(data: bytes, content_type: str) -> bool:
    """Files must look like what they claim to be. Plain text has no signature, so is checked
    only for NUL bytes."""
    signatures = _SIGNATURES.get(content_type)
    if signatures is None:
        return b"\x00" not in data[:1024]
    return data.startswith(signatures)


def safe_name(name: str) -> str:
    base = Path(name or "document").name
    return re.sub(r"[^\w.\- ()]", "_", base)[:200] or "document"


def _root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def save(case_id: uuid.UUID, upload: UploadFile) -> tuple[str, str, int, str]:
    """Stores the upload; returns (file_name, storage_key, size_bytes, content_type)."""
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "This file type is not allowed")
    limit = get_settings().max_upload_bytes
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")
    if not content_matches_type(data, content_type):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The file does not match its declared type"
        )
    try:
        SCANNER(data)
    except UnsafeUpload:
        raise HTTPException(422, "The file was rejected by the security scan") from None
    key = f"{case_id}/{uuid.uuid4().hex}"
    target = _root() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return safe_name(upload.filename or ""), key, len(data), content_type


def path_for(storage_key: str) -> Path:
    path = (_root() / storage_key).resolve()
    if _root() not in path.parents:  # never serve anything outside the upload folder
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return path
