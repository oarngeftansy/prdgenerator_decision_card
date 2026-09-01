from backend.calibration.models import make_source_ref, validate_artifact


def test_source_ref_and_evidence_levels():
    ref = make_source_ref("video", "level-1", "00:01:12.500")
    assert ref == {
        "sourceType": "video",
        "sourceId": "level-1",
        "locator": "00:01:12.500",
    }
    assert validate_artifact({"evidenceLevel": "certain"}, "evidence") == [
        "evidenceLevel must be one of observed, inferred, unknown"
    ]


def test_valid_evidence_requires_source_refs():
    assert validate_artifact({"evidenceLevel": "observed"}, "evidence") == [
        "evidence sourceRefs must be a non-empty list"
    ]
