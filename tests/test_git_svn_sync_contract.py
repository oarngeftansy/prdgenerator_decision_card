from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_git_svn.ps1"


def test_sync_orders_quality_git_push_before_svn_commit_and_never_embeds_password():
    text = SCRIPT.read_text(encoding="utf-8")
    lower = text.lower()

    assert lower.index("pytest") < lower.index("git push") < lower.index("svn commit")
    assert "xin.cheng" not in text
    assert "-SvnPassword" not in text
    assert "Read-Host -AsSecureString" in text


def test_sync_requires_git_remote_head_before_svn_write():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "remoteSha" in text
    assert "localSha" in text
    assert "GitHub remote SHA does not match local HEAD" in text
    assert "build_svn_release_package.ps1" in text
