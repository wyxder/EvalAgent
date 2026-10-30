"""Upload hardening: size, extension and filename checks."""

from __future__ import annotations

import os
import re

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".docx", ".pdf"}
_UNSAFE_FILENAME_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


def sanitize_filename(filename: str, max_length: int = 180) -> str:
    """Strip paths and control characters; keep a safe display filename."""

    base = os.path.basename(str(filename or "").replace("\\", "/"))
    cleaned = _UNSAFE_FILENAME_RE.sub("_", base).strip(" .")
    if not cleaned:
        cleaned = "upload"
    if len(cleaned) > max_length:
        stem, ext = os.path.splitext(cleaned)
        cleaned = f"{stem[: max_length - len(ext) - 8]}{ext}"
    return cleaned


def validate_upload(filename: str, size_bytes: int, max_mb: int) -> str:
    """Raise ``ValueError`` with a user-facing Chinese message when invalid."""

    safe_name = sanitize_filename(filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValueError(f"不支持的文件类型 {ext or '(无扩展名)'}，仅支持: {allowed}")
    max_bytes = max(1, max_mb) * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(f"文件过大：{safe_name} 超过 {max_mb} MB 上限")
    if size_bytes <= 0:
        raise ValueError(f"文件为空：{safe_name}")
    return safe_name
