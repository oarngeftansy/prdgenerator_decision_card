from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_pytest_collection_is_limited_to_project_tests():
    config = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "testpaths = tests" in config
    assert "ScreenCoder" in config and "runtime_packages" in config
