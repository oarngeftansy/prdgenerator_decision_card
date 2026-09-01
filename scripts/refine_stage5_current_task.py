from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "8312a91c89e144e6a59f81b982f14c06"
JOB_DIR = ROOT / "data" / "jobs" / JOB_ID
JOB_PATH = JOB_DIR / "job.json"


CHAPTER_COPY = {
    "GCH-001": {
        "normalFlow": [
            "进入关卡后，载具沿预设路线自动前进；玩家通过横向移动调整载具位置。",
            "横向移动用于避开敌人密集区域、调整武器覆盖位置或对准首领。",
            "载具受到有效攻击时扣除生命值，生命值归零后结束本局。",
        ],
        "keyRules": [
            "自动前进与横向操作同时生效，玩家不需要持续控制前进方向。",
            "横向移动受当前道路或可移动区域限制，拖动超出范围时停在边界。",
            "界面持续展示载具当前生命值，便于玩家判断继续战斗或规避伤害。",
        ],
        "specialCases": ["没有造成有效命中的攻击不扣除载具生命值。"],
    },
    "GCH-003": {
        "normalFlow": [
            "载具搭载的武器自动寻找攻击范围内的敌人，无需玩家逐次瞄准或点击攻击。",
            "不同武器占用各自的武器位置，并按照自身攻击方式产生投射物、范围伤害或持续伤害。",
            "攻击命中后在目标附近显示伤害数字，作为本次命中的即时反馈。",
        ],
        "keyRules": [
            "武器属性至少包含武器名称、等级和本次强化涉及的属性；这些信息同时用于强化选择与战斗结果判断。",
            "伤害、攻击范围等属性会改变实际攻击结果；素材只证明属性及变化值时，不额外推导隐藏计算公式。",
            "多个武器同时生效时分别执行各自的攻击逻辑，结算页再汇总各武器造成的伤害占比。",
        ],
        "specialCases": ["目标不在武器有效范围内时，该武器不应对该目标产生伤害。"],
    },
    "GCH-006": {
        "normalFlow": [
            "常规战斗阶段中，敌人随关卡推进持续出现，载具保持移动并自动攻击。",
            "达到首领阶段后，系统先显示首领来袭警告，再进入首领战。",
            "首领战展示独立生命值；玩家继续移动载具并依靠已获得的武器与强化进行攻击。",
            "首领在战斗过程中呈现不同攻击表现，玩家需要结合位置和当前生命值调整移动。",
            "首领生命值归零后结束战斗并进入关卡结算。",
        ],
        "keyRules": [
            "关卡计时、推进状态和首领生命值分别反映当前战斗阶段，不能互相替代。",
            "首领警告属于阶段切换反馈，不单独作为可操作页面。",
            "素材可证明首领存在多种攻击表现，但未提供攻击轮换条件，因此正文不编造固定轮换顺序。",
        ],
        "specialCases": ["首领战中载具生命值先归零时，直接按失败结束，不进入挑战成功结算。"],
    },
    "GCH-010": {
        "normalFlow": [
            "击败首领后进入挑战成功结算，停止局内战斗。",
            "结算页展示通关时间、获得的经验、金币和道具。",
            "伤害统计按武器汇总本局输出，帮助玩家判断本局主要伤害来源。",
        ],
        "keyRules": [
            "结算展示的是本局最终结果，不再参与当局伤害计算。",
            "载具生命值归零对应失败结果，与击败首领后的成功结果互斥。",
        ],
        "specialCases": ["双倍奖励和返回操作在截图中可见，但其消耗条件与发放规则没有可靠依据，需要通过决策卡或补充资料确定。"],
    },
    "GCH-012": {
        "normalFlow": [
            "触发升级后暂停战斗，并展示三个候选强化。",
            "候选卡片展示强化名称、关联武器和本次发生变化的属性，供玩家比较。",
            "玩家选择其中一项后，该强化立即加入本局并关闭选择界面，随后继续战斗。",
            "候选既可以解锁新武器，也可以提高已有武器的伤害、范围或其他可见属性。",
            "满足刷新条件时，玩家可以替换当前候选；刷新不等同于确认强化。",
        ],
        "keyRules": [
            "一次选择只应用一个候选，未选择的候选不会同时生效。",
            "属性变化按照卡片展示值应用；当前素材明确展示火焰喷射范围增加 30%、雷暴枪伤害增加 100%。",
            "强化卡片承担选择比较，玩法正文说明属性如何影响战斗，具体字段和值统一由配置表承载。",
        ],
        "specialCases": ["素材没有唯一证明升级触发条件和刷新消耗，因此未确认前不得写成固定规则。"],
    },
    "GCH-016": {
        "normalFlow": [
            "满足终极强化条件后，候选区出现具有特殊视觉标识的终极词条。",
            "玩家确认终极词条后，武器攻击方式发生结构性变化，例如由单向喷射改为同时向四个方向喷射。",
            "终极词条可能同时包含收益与代价；卡片需要在确认前完整展示两部分。",
        ],
        "keyRules": [
            "终极词条改变的是武器攻击逻辑，不应只作为普通数值提升处理。",
            "素材展示的伤害降低 20% 仅属于对应词条，不能推广为所有终极强化的固定代价。",
        ],
        "specialCases": ["终极词条的解锁条件没有被素材唯一证明，不能根据边框或出现顺序自行编造。"],
    },
    "GCH-018": {
        "normalFlow": [
            "进入抽取界面后，九宫格内容开始滚动，并在停止后形成武器或技能结果。",
            "结果确认后回到后续战斗流程；该方式与普通三选一强化分开处理。",
        ],
        "keyRules": [
            "当前素材只能证明九宫格滚动和结果展示，不能证明奖池权重、保底或合成公式。",
            "界面上的可见武器和技能属于候选内容，不能据此推导完整奖池。",
        ],
        "specialCases": ["抽取消耗、重复结果处理和跳过动画规则缺少唯一依据，需要补充资料或策划决策。"],
    },
}


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = JOB_DIR / f"job.before-stage5-refinement-{timestamp}.json"
    shutil.copy2(JOB_PATH, backup)

    review = job["reviewModel"]
    frame_titles: dict[str, str] = {}
    for stage in review.get("stages") or []:
        frame_ids = list(stage.get("sourceFrameIds") or [])
        frame_ids.extend(str(item.get("frameId") or "") for item in stage.get("representativeFrames") or [])
        for frame_id in frame_ids:
            frame_titles.setdefault(frame_id, str(stage.get("name") or "竞品画面"))

    target_dir = JOB_DIR / "reference_boards" / "competitor"
    target_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    for index, frame in enumerate(job.get("frames") or [], 1):
        frame_id = str(frame.get("id") or "")
        source = JOB_DIR / "frames" / f"{frame_id}.jpg"
        if not source.is_file():
            continue
        asset_id = f"CPA-{index:03d}"
        relative = Path("reference_boards") / "competitor" / f"{asset_id}.jpg"
        shutil.copy2(source, JOB_DIR / relative)
        assets.append({
            "id": asset_id,
            "relativePath": relative.as_posix(),
            "sourceName": f"{frame_titles.get(frame_id, '竞品画面')}｜截图 {index}",
            "order": index,
            "status": "ready",
            "kind": "competitor_reference",
            "sourceFrameId": frame_id,
        })
    review.setdefault("referenceBoards", {})["competitor"] = {
        "assets": assets,
        "status": "ready",
        "assetIdHighWater": len(assets),
        "source": "user_uploaded_screenshots",
    }
    review["revision"] = int(review.get("revision") or 0) + 1
    review.setdefault("reviewState", {})["previewRevision"] = None
    job.setdefault("metadata", {})["sourceImagesAreCompetitor"] = True

    gameplay = job["gameplayReviewModel"]
    for chapter in gameplay.get("chapters") or []:
        copy = CHAPTER_COPY.get(str(chapter.get("id") or ""))
        if not copy:
            continue
        sections = chapter.setdefault("plannerSections", {})
        sections.update(copy)
        chapter["plannerSectionsSource"] = "planner_refinement"
    gameplay["revision"] = int(gameplay.get("revision") or 0) + 1
    gameplay.setdefault("reviewState", {})["previewRevision"] = None
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()

    temporary = JOB_PATH.with_suffix(".stage5.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_PATH)
    print(json.dumps({
        "jobId": JOB_ID,
        "backup": str(backup),
        "competitorAssets": len(assets),
        "interactionRevision": review["revision"],
        "gameplayRevision": gameplay["revision"],
        "refinedChapters": len(CHAPTER_COPY),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
