from uuid import uuid4

from studyrag_backend.services.upload_storage import (
    remove_knowledge_base_uploads,
    remove_uploaded_file,
)


def test_completed_upload_is_removed_and_empty_directory_is_pruned(tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    task_dir = upload_root / str(uuid4())
    task_dir.mkdir(parents=True)
    uploaded = task_dir / "lesson.md"
    uploaded.write_text("# lesson", encoding="utf-8")

    assert remove_uploaded_file(upload_root, uploaded) is True
    assert not uploaded.exists()
    assert not task_dir.exists()


def test_upload_cleanup_refuses_paths_outside_root(tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside = tmp_path / "keep.md"
    outside.write_text("keep", encoding="utf-8")

    assert remove_uploaded_file(upload_root, outside) is False
    assert outside.exists()


def test_knowledge_base_cleanup_only_removes_its_isolated_directory(tmp_path) -> None:
    upload_root = tmp_path / "uploads"
    knowledge_base_id = uuid4()
    target = upload_root / str(knowledge_base_id)
    neighbour = upload_root / str(uuid4())
    target.mkdir(parents=True)
    neighbour.mkdir(parents=True)
    (target / "old.pdf").write_bytes(b"pdf")
    (neighbour / "keep.txt").write_text("keep", encoding="utf-8")

    assert remove_knowledge_base_uploads(upload_root, knowledge_base_id) is True
    assert not target.exists()
    assert neighbour.exists()
