import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "svn-release-manifest.json"


def test_svn_release_manifest_includes_runtime_and_excludes_secrets_and_caches():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert "runtime_packages_server" in manifest["dependencyRoots"]
    assert "runtime_packages_pytest" in manifest["dependencyRoots"]
    assert ".git" in manifest["excludeNames"]
    assert ".pytest_cache" in manifest["excludeNames"]
    assert any("credential" in pattern.lower() for pattern in manifest["secretPatterns"])
    assert manifest["sourceMode"] == "git_head_plus_dependency_whitelist"
    assert ".env.example" in manifest["allowedSecretTemplateNames"]


def test_release_builder_filters_excluded_dependency_paths_before_validation():
    script = (ROOT / "scripts" / "build_svn_release_package.ps1").read_text(encoding="utf-8")

    assert "Copy-FilteredTree" in script
    assert "Get-CompatibleRelativePath" in script
    assert "[System.IO.Path]::GetRelativePath" not in script
    assert "$manifest.excludeNames -contains $_.Name" in script
    assert "allowedSecretTemplateNames" in script


def test_release_manifest_never_contains_credentials():
    text = MANIFEST.read_text(encoding="utf-8")

    assert "xin.cheng" not in text
    assert '"password"' not in text.lower()
