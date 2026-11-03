"""Durably retain validated canonical source bundles."""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings

from emporio.sources.read import SourceImportError


def _retain_bundle(source: Path, version: str, manifest: dict[str, Any]) -> None:
    """Durably stage validated canonical files before their SQLite snapshot activates."""
    root = Path(
        getattr(settings, "EMPORIO_BUNDLE_ROOT", Path(settings.BASE_DIR) / ".source-bundles")
    ).resolve()
    static = Path(
        getattr(settings, "STATIC_ROOT", None) or Path(settings.BASE_DIR) / "static"
    ).resolve()
    if root == static or static in root.parents:
        raise SourceImportError("bundle storage must be outside static storage")
    target = root / version
    expected = _expected_bundle_hashes(manifest)
    if target.exists():
        _verify_bundle(target, expected)
        return
    _ensure_bundle_root(root)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
    _stage_bundle(source, target, staging, expected)


def _expected_bundle_hashes(manifest):
    return {
        **{
            f"desafio_tecnico_ai_eng - {name}.csv": digest
            for name, digest in manifest["csv_sha256"].items()
        },
        "políticas_da_loja.pdf": manifest["pdf_sha256"],
    }


def _ensure_bundle_root(root):
    missing = []
    current = root
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise SourceImportError("bundle storage parent is not a directory")
    for directory in reversed(missing):
        directory.mkdir()
        _fsync_directory(directory.parent)
    _fsync_directory(root)


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_bundle(target, expected):
    if not _bundle_matches(target, expected):
        raise SourceImportError("retained source bundle failed hash verification")


def _bundle_matches(target, expected):
    return (
        target.is_dir()
        and {path.name for path in target.iterdir()} == set(expected)
        and all(_matches_hash(target / name, digest) for name, digest in expected.items())
    )


def _matches_hash(path, expected):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected


def _stage_bundle(source, target, staging, expected):
    try:
        _copy_verified_files(source, staging, expected)
        _sync_staged_files(staging)
        _fsync_directory(staging)
        os.replace(staging, target)
        _fsync_directory(target.parent)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _copy_verified_files(source, staging, expected):
    for name in expected:
        shutil.copyfile(source / name, staging / name)
    for name, digest in expected.items():
        if not _matches_hash(staging / name, digest):
            raise SourceImportError("staged source bundle failed hash verification")


def _sync_staged_files(staging):
    for path in staging.iterdir():
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
