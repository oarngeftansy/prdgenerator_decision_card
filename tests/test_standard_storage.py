import json

from backend import storage


def test_list_standards_hides_corrupted_placeholder_names(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STANDARDS_ROOT", tmp_path)
    (tmp_path / "valid.json").write_text(
        json.dumps({"id": "valid", "name": "战斗策划规范", "createdAt": "2026-08-13"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "broken.json").write_text(
        json.dumps({"id": "broken", "name": "??????", "createdAt": "2026-08-14"}),
        encoding="utf-8",
    )

    assert [record["id"] for record in storage.list_standards()] == ["valid"]
