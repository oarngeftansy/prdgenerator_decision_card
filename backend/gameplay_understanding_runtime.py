"""Runtime owner for Gameplay Understanding Skill v1.2.

This stage consumes evidence frames and produces the first-class
GameplayUnderstandingModel. A legacy gameplayReviewModel is projected only as a
compatibility shell for the existing review UI; it is not the semantic authority.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from .analysis_service import _call, _client
from .gameplay_directory import synthesize_directory
from .gameplay_review_model import build_gameplay_review_model, normalize_gameplay_structure
from .planning_skill_contract import load_production_skill
from .planning_gameplay_sync import sync_planning_gameplay_insights


class GameplayUnderstandingError(ValueError):
    pass


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _title_key(value: Any) -> str:
    text = re.sub(r"[\s\-—_·:：/（）()]+", "", str(value or "").casefold())
    return re.sub(r"(?:玩法)?(?:系统|子系统|机制|规则)$", "", text)


def _runtime_prompt(frame_ids: list[str]) -> str:
    contract = load_production_skill("gameplay_understanding")
    return f"""{contract}

## Runtime task

Analyze the ordered evidence frames and execute Gameplay Understanding Skill v1.2. Return one JSON object only. Discover the project's hierarchy from the evidence; there is no maximum mechanism count per subsystem and no fixed list of gameplay families.

Output schema:
{{
  "summary":"简洁玩法理解",
  "coreLoop":["步骤"],
  "systems":[{{
    "name":"系统",
    "reason":"为什么属于同一系统",
    "subsystems":[{{
      "name":"子系统",
      "mechanisms":[{{
        "name":"具体机制",
        "reason":"行为/状态层面的机制依据，不是页面描述",
        "sourceFrameIds":["F0001"],
        "ruleGroups":[{{"name":"规则责任组","summary":"该组解释的行为责任"}}]
      }}]
    }}]
  }}]
}}

Runtime constraints:
- sourceFrameIds may only use the supplied IDs.
- Mechanism names describe independently reviewable gameplay behavior; do not use page/button/panel/color/effect as the mechanism itself.
- Infer hidden mechanics from ordered behavior/state changes when needed. Evidence weakness is not a reason to stop reconstruction.
- Do not insert “待确认/可能/推测” into semantic copy; provenance belongs to metadata.
- Do not inject skills, weapons, monsters, candidate pools, shops, combat, waves or any other sample nouns unless this project actually contains them.
- Do not cap mechanisms per subsystem. Split only when the current project's real responsibilities warrant it.
- ruleGroups are dynamic responsibilities, not a fixed schema.
- This stage does not design parameters, formulas, implementation fields, Final prose or P4-P7 content.

Supplied frame IDs:
{json.dumps(frame_ids, ensure_ascii=False)}"""


def _validate_response(value: Any, known_frame_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("systems"), list) or not value["systems"]:
        raise GameplayUnderstandingError("Gameplay Understanding must return non-empty systems")
    result: dict[str, Any] = {
        "summary": str(value.get("summary") or "").strip(),
        "coreLoop": [str(item).strip() for item in (value.get("coreLoop") or []) if str(item).strip()],
        "systems": [],
    }
    seen_systems: set[str] = set()
    seen_mechanisms: set[tuple[str, str, str]] = set()
    for raw_system in value["systems"]:
        if not isinstance(raw_system, dict) or not str(raw_system.get("name") or "").strip():
            raise GameplayUnderstandingError("system name is required")
        system_name = str(raw_system["name"]).strip()
        system_key = _title_key(system_name)
        if not system_key or system_key in seen_systems:
            raise GameplayUnderstandingError("duplicate gameplay system")
        seen_systems.add(system_key)
        system = {"name": system_name, "reason": str(raw_system.get("reason") or "").strip(), "subsystems": []}
        for raw_subsystem in raw_system.get("subsystems") or []:
            if not isinstance(raw_subsystem, dict) or not str(raw_subsystem.get("name") or "").strip():
                raise GameplayUnderstandingError("subsystem name is required")
            subsystem_name = str(raw_subsystem["name"]).strip()
            subsystem = {"name": subsystem_name, "mechanisms": []}
            for raw_mechanism in raw_subsystem.get("mechanisms") or []:
                if not isinstance(raw_mechanism, dict) or not str(raw_mechanism.get("name") or "").strip():
                    raise GameplayUnderstandingError("mechanism name is required")
                mechanism_name = str(raw_mechanism["name"]).strip()
                ids = list(dict.fromkeys(
                    item for item in (raw_mechanism.get("sourceFrameIds") or [])
                    if isinstance(item, str)
                ))
                if not ids or any(item not in known_frame_ids for item in ids):
                    raise GameplayUnderstandingError("mechanism cites unknown evidence frame")
                identity = (system_key, _title_key(subsystem_name), _title_key(mechanism_name))
                if not identity[2] or identity in seen_mechanisms:
                    raise GameplayUnderstandingError("duplicate gameplay mechanism")
                seen_mechanisms.add(identity)
                rule_groups = []
                for raw_group in raw_mechanism.get("ruleGroups") or []:
                    if not isinstance(raw_group, dict):
                        continue
                    name = str(raw_group.get("name") or "").strip()
                    summary = str(raw_group.get("summary") or "").strip()
                    if name:
                        rule_groups.append({"name": name, "summary": summary})
                subsystem["mechanisms"].append({
                    "name": mechanism_name,
                    "reason": str(raw_mechanism.get("reason") or "").strip(),
                    "sourceFrameIds": ids,
                    "ruleGroups": rule_groups,
                })
            if subsystem["mechanisms"]:
                system["subsystems"].append(subsystem)
        if system["subsystems"]:
            result["systems"].append(system)
    if not result["systems"]:
        raise GameplayUnderstandingError("Gameplay Understanding produced zero mechanisms")
    return result


def _first_class_model(structure: dict[str, Any], *, source_revision: int | None = None) -> dict[str, Any]:
    systems = []
    mechanisms = []
    rule_groups = []
    system_graph = {"systems": []}
    for system_index, system in enumerate(structure["systems"], 1):
        system_id = f"SYS-{system_index:03d}"
        system_entry = {"systemId": system_id, "name": system["name"], "reason": system.get("reason") or "", "subsystems": []}
        graph_system = {"systemId": system_id, "subsystems": []}
        for subsystem_index, subsystem in enumerate(system["subsystems"], 1):
            subsystem_id = f"{system_id}-SUB-{subsystem_index:03d}"
            subsystem_entry = {"subsystemId": subsystem_id, "name": subsystem["name"], "mechanismIds": []}
            graph_sub = {"subsystemId": subsystem_id, "mechanisms": []}
            for mechanism_index, mechanism in enumerate(subsystem["mechanisms"], 1):
                mechanism_id = f"{subsystem_id}-MEC-{mechanism_index:03d}"
                mechanism_entry = {
                    "mechanicId": mechanism_id,
                    "systemId": system_id,
                    "subsystemId": subsystem_id,
                    "name": mechanism["name"],
                    "summary": mechanism.get("reason") or "",
                    "sourceFrameIds": deepcopy(mechanism["sourceFrameIds"]),
                    "ruleGroupIds": [],
                }
                for group_index, group in enumerate(mechanism.get("ruleGroups") or [], 1):
                    group_id = f"{mechanism_id}-RG-{group_index:03d}"
                    mechanism_entry["ruleGroupIds"].append(group_id)
                    rule_groups.append({
                        "ruleGroupId": group_id,
                        "mechanicId": mechanism_id,
                        "name": group["name"],
                        "summary": group.get("summary") or "",
                    })
                mechanisms.append(mechanism_entry)
                subsystem_entry["mechanismIds"].append(mechanism_id)
                graph_sub["mechanisms"].append(mechanism_id)
            system_entry["subsystems"].append(subsystem_entry)
            graph_system["subsystems"].append(graph_sub)
        systems.append(system_entry)
        system_graph["systems"].append(graph_system)
    model = {
        "version": "gameplay_understanding_model_v1_2",
        "skillContract": "gameplay-understanding-v1.2",
        "sourceRevision": source_revision,
        "summary": structure.get("summary") or "",
        "coreLoop": deepcopy(structure.get("coreLoop") or []),
        "systems": systems,
        "systemGraph": system_graph,
        "mechanisms": mechanisms,
        "ruleGroups": rule_groups,
    }
    model["digest"] = _digest(model)
    return model


def _compatibility_review_model(job: dict[str, Any], structure: dict[str, Any], understanding: dict[str, Any]) -> dict[str, Any]:
    drafts = []
    for system in structure["systems"]:
        for subsystem in system["subsystems"]:
            for mechanism in subsystem["mechanisms"]:
                reason = mechanism.get("reason") or f"{mechanism['name']}由当前行为与状态序列构成"
                drafts.append({
                    "title": mechanism["name"],
                    "systemName": system["name"],
                    "subsystemName": subsystem["name"],
                    # `custom` is a compatibility adapter only. It must never be
                    # treated as the semantic mechanism taxonomy.
                    "mechanismType": "custom",
                    "sourceFrameIds": deepcopy(mechanism["sourceFrameIds"]),
                    "claims": [{
                        "text": reason,
                        "sourceType": "inference",
                        "sourceFrameIds": deepcopy(mechanism["sourceFrameIds"]),
                    }],
                    "mechanism": {"type": "custom", "description": reason},
                    "parameters": {},
                    "dependencies": [],
                    "acceptanceCases": [],
                    "unknowns": [],
                    "confidence": "understanding-v1.2",
                })
    if not drafts:
        raise GameplayUnderstandingError("cannot project empty understanding into review compatibility model")
    model = build_gameplay_review_model(job, drafts, directory_proposal=synthesize_directory(drafts))
    model.update(normalize_gameplay_structure(model))
    directory = model.setdefault("directory", {})
    directory["understanding"] = {
        "version": understanding["version"],
        "skillContract": understanding["skillContract"],
        "digest": understanding["digest"],
        "Summary": understanding.get("summary") or "",
        "CoreLoop": deepcopy(understanding.get("coreLoop") or []),
        "Systems": deepcopy(understanding.get("systems") or []),
        "SystemGraph": deepcopy(understanding.get("systemGraph") or {}),
        "Mechanisms": deepcopy(understanding.get("mechanisms") or []),
        "RuleGroups": deepcopy(understanding.get("ruleGroups") or []),
    }
    state = model.setdefault("reviewState", {})
    state.update({
        "status": "system_directory_review",
        "structurePhase": "systems",
        "previewRevision": None,
        "understandingContract": "gameplay-understanding-v1.2",
    })
    model["understandingDigest"] = understanding["digest"]
    return sync_planning_gameplay_insights(job, model)


def generate_gameplay_understanding(
    job: dict[str, Any],
    job_dir: Path,
    runtime_config: dict[str, Any],
    progress: Callable[[int, str], None] = lambda *_: None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate first-class understanding and a compatibility review projection."""
    frames = [item for item in (job.get("frames") or []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if not frames:
        raise GameplayUnderstandingError("Gameplay Understanding requires evidence frames")
    frame_ids = [item["id"] for item in frames]
    images = [
        (f"frame={item['id']} index={index}", job_dir / "frames" / Path(str(item.get("imageUrl") or "")).name)
        for index, item in enumerate(frames, 1)
    ]
    client = _client(runtime_config)
    if client is None:
        raise GameplayUnderstandingError("gameplay understanding model is unavailable")
    model_name = str(runtime_config.get("model") or "qwen3.6plus")
    progress(10, "正在执行 Gameplay Understanding v1.2")
    try:
        response = _call(client, model_name, _runtime_prompt(frame_ids), images, max_tokens=6500)
    except Exception as exc:
        raise GameplayUnderstandingError("Gameplay Understanding model request failed") from exc
    structure = _validate_response(response, set(frame_ids))
    understanding = _first_class_model(structure, source_revision=(job.get("gameplayReviewModel") or {}).get("revision"))
    progress(75, "正在建立动态玩法系统图")
    compatibility = _compatibility_review_model(job, structure, understanding)
    progress(100, "Gameplay Understanding v1.2 已完成")
    return understanding, compatibility
