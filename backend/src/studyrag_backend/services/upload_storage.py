from pathlib import Path
from shutil import rmtree
from uuid import UUID


def _contained_path(root: Path, candidate: Path) -> Path | None:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate == resolved_root or resolved_root not in resolved_candidate.parents:
        return None
    return resolved_candidate


def remove_uploaded_file(upload_dir: Path, stored_path: str | Path) -> bool:
    """Remove one task upload without ever following a path outside upload_dir."""
    root = upload_dir.resolve()
    candidate = _contained_path(root, Path(stored_path))
    if candidate is None:
        return False
    candidate.unlink(missing_ok=True)

    parent = candidate.parent
    while parent != root and root in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    return True


def remove_knowledge_base_uploads(upload_dir: Path, knowledge_base_id: UUID) -> bool:
    """Remove the isolated upload directory owned by one knowledge base."""
    root = upload_dir.resolve()
    target = _contained_path(root, root / str(knowledge_base_id))
    if target is None or not target.exists():
        return False
    rmtree(target)
    return True
