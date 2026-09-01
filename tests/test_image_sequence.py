import io
import json
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image


def png_bytes(color=(20, 40, 80)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (12, 20), color).save(output, format="PNG")
    return output.getvalue()


def upload(name: str, payload: bytes | None = None, content_type: str = "image/png") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(payload or png_bytes()), headers={"content-type": content_type})


def manifest(names: list[str]) -> str:
    return json.dumps([
        {"clientId": f"IMG{index:03d}", "originalName": name, "order": index}
        for index, name in enumerate(names, 1)
    ])


def test_persists_manifest_order_as_stable_frames(tmp_path, monkeypatch):
    from backend import image_sequence

    class FakeAdapter:
        def analyze(self, _path, _structures_dir):
            return {"engine": "test", "elementCount": 0, "elements": [], "regionCounts": {}}

    monkeypatch.setattr(image_sequence, "ScreenCoderAdapter", FakeAdapter)
    frames, scenes, tracks = image_sequence.persist_image_sequence(
        tmp_path,
        [upload("10.png"), upload("2.png")],
        manifest(["2.png", "10.png"]),
    )

    assert [(item["id"], item["sourceName"], item["sequenceIndex"], item["sceneId"]) for item in frames] == [
        ("F0001", "2.png", 1, 0),
        ("F0002", "10.png", 2, 1),
    ]
    assert [scene["frameIds"] for scene in scenes] == [["F0001"], ["F0002"]]
    assert tracks == []
    assert all((tmp_path / "frames" / Path(frame["imageUrl"]).name).exists() for frame in frames)
    assert sorted(path.name for path in (tmp_path / "source_images").iterdir()) == ["F0001.png", "F0002.png"]
    assert json.loads((tmp_path / "image-import-manifest.json").read_text(encoding="utf-8"))["status"] == "complete"


def test_recovers_a_fully_persisted_image_sequence_after_restart(tmp_path, monkeypatch):
    from backend import image_sequence

    class FakeAdapter:
        def analyze(self, image_path, structures_dir):
            structure = {"engine": "test", "elementCount": 0, "elements": [], "regionCounts": {}, "source": image_path.name}
            (structures_dir / f"{image_path.stem}.structure.json").write_text(json.dumps(structure), encoding="utf-8")
            return structure

    monkeypatch.setattr(image_sequence, "ScreenCoderAdapter", FakeAdapter)
    expected = image_sequence.persist_image_sequence(
        tmp_path,
        [upload("1.png"), upload("2.png")],
        manifest(["1.png", "2.png"]),
    )

    recovered = image_sequence.recover_persisted_image_sequence(tmp_path)

    assert [frame["id"] for frame in recovered[0]] == ["F0001", "F0002"]
    assert [frame["sourceName"] for frame in recovered[0]] == ["1.png", "2.png"]
    assert [scene["frameIds"] for scene in recovered[1]] == [["F0001"], ["F0002"]]
    assert recovered[2] == expected[2]


def test_persists_frames_when_job_path_contains_chinese_characters(tmp_path, monkeypatch):
    from backend import image_sequence

    class FakeAdapter:
        def analyze(self, _path, _structures_dir):
            return {"engine": "test", "elementCount": 0, "elements": [], "regionCounts": {}}

    monkeypatch.setattr(image_sequence, "ScreenCoderAdapter", FakeAdapter)
    job_dir = tmp_path / "中文任务"

    frames, _, _ = image_sequence.persist_image_sequence(
        job_dir,
        [upload("1.png"), upload("2.png")],
        manifest(["1.png", "2.png"]),
    )

    assert [Path(frame["imageUrl"]).name for frame in frames] == ["F0001.jpg", "F0002.jpg"]
    assert (job_dir / "frames" / "F0001.jpg").read_bytes().startswith(b"\xff\xd8")
    assert (job_dir / "frames" / "F0002.jpg").read_bytes().startswith(b"\xff\xd8")


@pytest.mark.parametrize("count", [1, 51])
def test_rejects_counts_outside_contract(tmp_path, count):
    from backend.image_sequence import ImageSequenceError, persist_image_sequence

    names = [f"{index}.png" for index in range(count)]
    with pytest.raises(ImageSequenceError, match="2.*50"):
        persist_image_sequence(tmp_path, [upload(name) for name in names], manifest(names))


@pytest.mark.parametrize(
    ("uploads", "manifest_json", "message"),
    [
        ([upload("a.gif", content_type="image/gif"), upload("b.png")], manifest(["a.gif", "b.png"]), "格式"),
        ([upload("a.png", b"broken"), upload("b.png")], manifest(["a.png", "b.png"]), "损坏"),
        ([upload("a.png"), upload("b.png")], manifest(["a.png"]), "数量"),
        ([upload("a.png"), upload("b.png")], json.dumps([
            {"clientId": "A", "originalName": "a.png", "order": 1},
            {"clientId": "B", "originalName": "b.png", "order": 1},
        ]), "顺序"),
    ],
)
def test_rejects_invalid_files_and_manifests(tmp_path, uploads, manifest_json, message):
    from backend.image_sequence import ImageSequenceError, persist_image_sequence

    with pytest.raises(ImageSequenceError, match=message):
        persist_image_sequence(tmp_path, uploads, manifest_json)
