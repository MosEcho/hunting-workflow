"""Local file helpers. No network operations."""
import hashlib
import json
from pathlib import Path


class WorkflowError(ValueError):
    """An actionable input or output error."""


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"无法读取 JSON / Cannot read JSON: {path}: {exc}") from exc


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside_file(base, relative):
    """Require a regular, non-symlink file inside the case directory."""
    if not isinstance(relative, str) or not relative:
        raise WorkflowError("证据路径为空 / Empty evidence path")
    # Interpret both separators consistently, including when checking Windows data on POSIX.
    normalized = relative.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise WorkflowError("证据路径必须位于案例内 / Evidence path must stay inside case")
    base = Path(base).resolve()
    candidate = base.joinpath(*normalized.split("/"))
    current = base
    for part in normalized.split("/"):
        current = current / part
        if current.is_symlink():
            raise WorkflowError("证据不接受软链接 / Symlink evidence is not accepted")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(base) or not resolved.is_file():
        raise WorkflowError("证据文件不存在或越界 / Missing or out-of-case evidence")
    return resolved


def new_directory(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise WorkflowError(f"输出已存在，请使用新目录 / Output exists, use a new directory: {path}")
    path.mkdir(parents=True)
    return path
