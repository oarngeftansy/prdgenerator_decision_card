from __future__ import annotations

from collections import Counter
from typing import Any


def validate_stage3_evidence(entries: list[dict[str, Any]], *, official_before: str, official_after: str) -> dict[str, Any]:
    expected_ids = [f"S3-TC{index:02d}" for index in range(1, 31)]
    ids = [str(item.get("caseId") or "") for item in entries]
    findings: list[str] = []
    if ids != expected_ids:
        missing = [item for item in expected_ids if item not in ids]
        duplicate_ids = [item for item, count in Counter(ids).items() if item and count > 1]
        findings.append(f"用例编号不完整或顺序错误；缺少：{missing or '无'}；重复：{duplicate_ids or '无'}")
    for field, label in (("inputHash", "输入"), ("bodyHash", "正文"), ("screenshotHash", "截图")):
        values = [str(item.get(field) or "") for item in entries]
        duplicates = [value for value, count in Counter(values).items() if value and count > 1]
        if any(not value for value in values):
            findings.append(f"存在没有{label}哈希的用例")
        if duplicates:
            findings.append(f"存在重复{label}哈希：{duplicates}")
    for item in entries:
        if item.get("visibleCaseId") != item.get("caseId"):
            findings.append(f"{item.get('caseId') or '未知用例'} 的截图身份与证据记录不一致")
        if item.get("humanInspected") is not True:
            findings.append(f"{item.get('caseId') or '未知用例'} 尚未完成人工目检")
    if not official_before or official_before != official_after:
        findings.append("正式任务执行前后哈希不一致")
    return {"passed": not findings, "findings": findings, "caseCount": len(entries), "officialJobUnchanged": bool(official_before and official_before == official_after)}
