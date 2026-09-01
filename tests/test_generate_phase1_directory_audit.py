from scripts.generate_phase1_directory_audit import HIGH_RISK_OWNERS, _blind_fixture
from backend.phase1_directory import build_phase1_directory


def test_audit_covers_all_requested_high_risk_titles():
    assert tuple(HIGH_RISK_OWNERS) == (
        "武器解锁、攻击与词条成长",
        "武器命中、反馈与伤害归集",
        "攻击、养成与词条生效",
        "解锁、养成与词条进入随机池",
        "候选、刷新与确认",
        "终极词条进入与生效",
        "滚动、跳过与结果",
        "刷新、作战与首领阶段",
    )


def test_blind_fixture_has_stable_titles_without_project_specific_inventions():
    result = build_phase1_directory(_blind_fixture())
    tree = result["humanReadableTree"]
    assert "卡牌对局" in tree
    assert all(value not in tree for value in ("载具", "武器", "GVE16"))
    assert result["qualityReport"]["customCount"] == 0
