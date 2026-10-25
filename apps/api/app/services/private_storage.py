from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile


class PrivateStorageError(ValueError):
    pass


def _owner_directory(owner_id: str) -> str:
    return hashlib.sha256(owner_id.encode("utf-8")).hexdigest()


def store_private_pdf(source_path: Path, storage_root: Path, owner_id: str, sha256: str) -> Path:
    """Copy a verified PDF into an owner-isolated private directory."""
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise PrivateStorageError("Invalid source checksum")
    root = storage_root.resolve()
    owner_dir = (root / _owner_directory(owner_id)).resolve()
    if root not in owner_dir.parents:
        raise PrivateStorageError("Resolved private storage path escapes its root")
    owner_dir.mkdir(parents=True, exist_ok=True)
    target = owner_dir / f"{sha256}.pdf"
    if target.exists():
        if _file_sha256(target) != sha256:
            raise PrivateStorageError("Existing private source does not match its checksum")
        return target

    descriptor, temporary_name = tempfile.mkstemp(prefix=".import-", dir=owner_dir)
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(source_path, temporary_path)
        if _file_sha256(temporary_path) != sha256:
            raise PrivateStorageError("Source changed while being copied to private storage")
        temporary_path.replace(target)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target


def remove_private_file(path: Path, storage_root: Path, owner_id: str) -> None:
    root = storage_root.resolve()
    owner_dir = (root / _owner_directory(owner_id)).resolve()
    candidate = path.resolve()
    if owner_dir not in candidate.parents or candidate.suffix.lower() != ".pdf":
        raise PrivateStorageError("Refusing to delete a file outside the owner's private storage")
    candidate.unlink(missing_ok=True)


def stage_private_file_deletion(path: Path, storage_root: Path, owner_id: str) -> Path:
    root = storage_root.resolve()
    owner_dir = (root / _owner_directory(owner_id)).resolve()
    candidate = path.resolve()
    if owner_dir not in candidate.parents or candidate.suffix.lower() != ".pdf":
        raise PrivateStorageError("Refusing to delete a file outside the owner's private storage")
    if not candidate.exists():
        return candidate.with_suffix(".pdf.deleting")
    staged = candidate.with_suffix(".pdf.deleting")
    candidate.replace(staged)
    return staged


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
