from __future__ import annotations

from dataclasses import replace

from .planning_content_models import ApplicabilityPredicate, ChapterSchema, DerivationSpec, GapPolicy, GroupingStrategy, SchemaSlotDefinition


SCHEMA_VERSION = "chapter-schema-v2"


def _tag(value: str) -> ApplicabilityPredicate:
    return ApplicabilityPredicate("evidence_tag", (value,))


def _any(*values: str) -> ApplicabilityPredicate:
    return ApplicabilityPredicate("any", tuple(_tag(value) for value in values))


def _slot(slot_id: str, applicability: str, types: tuple[str, ...], group: str, question: str | None = None, predicate: ApplicabilityPredicate | None = None, derivation: DerivationSpec | None = None, severity: str = "qa_blocking", probe_type: str | None = None, target_property: str | None = None, gap_domain: str = "planning", inference_permission: str = "evidence_required") -> SchemaSlotDefinition:
    gap = GapPolicy("implementation_blocking" if applicability == "core" else severity, question, probe_type, target_property, gap_domain, inference_permission) if question else None
    return SchemaSlotDefinition(slot_id, applicability, types, predicate, derivation, gap, group)


def _schema(chapter_type: str, title: str, slots: tuple[SchemaSlotDefinition, ...], groups: tuple[str, ...]) -> ChapterSchema:
    return ChapterSchema(SCHEMA_VERSION, chapter_type, None, title, slots, GroupingStrategy(groups))


_BASE = (
    _schema("movement", "移动", (
        _slot("movement_trigger", "core", ("logic", "flow"), "movement_core", "{object}在什么条件下开始移动？"),
        _slot("movement_direction", "conditional", ("logic",), "movement_core", "{object}的移动方向或目标如何确定？", _any("directional", "follow", "targeted")),
        _slot("movement_control", "conditional", ("interaction",), "movement_core", "玩家如何控制或修正移动？", _any("manual_control", "steering")),
        _slot("movement_speed_source", "core", ("numeric", "config"), "movement_core", "{object}的移动速度读取哪项配置，生效单位是什么？", gap_domain="technical"),
        _slot("movement_rate_change", "optional", ("logic",), "movement_core"),
        _slot("movement_path", "conditional", ("logic",), "movement_constraints", "路径如何确定？", _any("pathfinding", "waypoint", "bounded_path")),
        _slot("movement_collision", "conditional", ("logic",), "movement_constraints", "碰撞如何处理？", _any("collision", "obstacle")),
        _slot("movement_stop_condition", "core", ("logic", "flow"), "movement_core", "{object}在什么条件下停止移动？"),
        _slot("movement_duration", "derived", ("flow",), "movement_core", derivation=DerivationSpec(("movement_trigger", "movement_stop_condition"), "derive_active_interval")),
        _slot("movement_presentation", "presentation_only", ("presentation",), "presentation", "移动表现如何定义？", _any("movement_animation", "movement_vfx"), severity="documentation_gap"),
    ), ("movement_core", "movement_constraints", "presentation")),
    _schema("attack", "攻击", (
        _slot("attack_trigger", "core", ("logic",), "attack_core", "{object}在什么条件下开始攻击？"),
        _slot("attack_target", "core", ("logic",), "attack_core", "{object}如何选择攻击目标，目标失效时如何处理？"),
        _slot("attack_range", "conditional", ("numeric", "config"), "parameters", "{object}的攻击距离读取哪项配置，距离判定以哪个对象位置为准？", _any("range", "melee", "ranged"), severity="implementation_blocking", gap_domain="technical"),
        _slot("attack_frequency", "conditional", ("numeric", "config"), "parameters", "攻击频率如何确定？", _any("repeat", "cooldown"), severity="implementation_blocking"),
        _slot("attack_method", "core", ("logic",), "attack_core", "{object}命中目标前依次执行哪些攻击处理？"),
        _slot("attack_exit_condition", "core", ("logic", "flow"), "attack_core", "{object}在什么条件下退出攻击状态？"),
        _slot("damage_reference", "conditional", ("logic", "config"), "parameters", "{object}命中后引用哪条伤害计算规则，伤害结果传递给哪个对象？", _tag("damage"), severity="implementation_blocking", gap_domain="technical"),
        _slot("attack_presentation", "presentation_only", ("presentation",), "presentation", "攻击表现如何定义？", _any("attack_vfx", "attack_sfx"), severity="documentation_gap"),
    ), ("attack_core", "parameters", "presentation")),
    _schema("slot", "栏位", (
        _slot("slot_count", "core", ("numeric", "config"), "definition", "{object}可用栏位数量是多少？"),
        _slot("initial_state", "core", ("logic", "config"), "lifecycle", "进入关卡时，{object}栏位的初始占用状态和默认内容是什么？"),
        _slot("fill_condition", "core", ("logic", "interaction"), "lifecycle", "玩家通过什么行为向{object}栏位填入内容，填入在什么时点生效？"),
        _slot("full_slot_rule", "conditional", ("logic",), "constraints", "满栏后如何处理？", _any("finite_slots", "slot_full")),
        _slot("replace_rule", "conditional", ("logic", "interaction"), "operations", "如何替换？", _tag("replace")),
        _slot("display_content", "presentation_only", ("presentation",), "presentation", "栏位显示什么？", _tag("slot_ui"), severity="documentation_gap"),
    ), ("definition", "lifecycle", "operations", "constraints", "presentation")),
    _schema("randomization", "随机", (
        _slot("random_trigger", "core", ("logic", "flow"), "flow", "随机流程如何触发？"),
        _slot("candidate_pool_source", "core", ("config",), "pool", "候选池读取哪份已确认配置或数据集合？", gap_domain="technical"),
        _slot("pool_entry_condition", "core", ("logic", "config"), "pool", "候选项满足哪些条件后可以进入本次候选池？"),
        _slot("pool_exit_condition", "conditional", ("logic", "config"), "pool", "候选项在什么条件下移出候选池？", _any("three_choice", "roulette"), severity="implementation_blocking"),
        _slot("duplicate_rule", "conditional", ("logic", "config"), "draw", "同一次候选生成中是否允许出现重复项？", _tag("duplicate"), severity="qa_blocking"),
        _slot("replacement_rule", "conditional", ("logic", "config"), "draw", "候选项被抽取后是否放回候选池？", _tag("replacement"), severity="qa_blocking"),
        _slot("weight_rule", "conditional", ("numeric", "config"), "draw", "各候选项的抽取权重如何确定？", _tag("weight"), severity="implementation_blocking"),
        _slot("candidate_effect", "conditional", ("logic",), "draw", "候选项生效后改变什么？", _any("candidate", "three_choice"), severity="implementation_blocking"),
        _slot("effect_parameter", "conditional", ("numeric", "config"), "draw", "候选效果包含哪些数值变化？", _any("candidate", "three_choice"), severity="implementation_blocking"),
        _slot("candidate_selection", "conditional", ("interaction",), "flow", "玩家如何从候选项中完成选择？", _tag("three_choice"), severity="qa_blocking"),
        _slot("empty_result_rule", "core", ("logic", "flow"), "exceptions", "没有合法候选项时，当前随机流程如何继续或退出？"),
        _slot("max_level_rule", "conditional", ("logic", "config"), "exceptions", "候选项达到最大等级后如何处理？", _tag("max_level"), severity="implementation_blocking"),
        _slot("prerequisite_rule", "conditional", ("logic", "config"), "pool", "候选项存在前置关系时，前置条件如何判定？", _tag("prerequisite"), severity="implementation_blocking"),
        _slot("refresh_rule", "conditional", ("logic", "interaction"), "refresh", "刷新如何执行？", _tag("refresh")),
        _slot("refresh_count", "conditional", ("numeric", "config"), "refresh", "单次选择流程允许刷新多少次？", _tag("refresh"), severity="qa_blocking"),
        _slot("refresh_cost", "conditional", ("numeric", "config"), "refresh", "刷新采用资源消耗还是广告条件；资源类型、数量和扣除时点分别是什么？", _tag("refresh"), severity="implementation_blocking"),
        _slot("selection_pause", "conditional", ("flow", "logic"), "flow", "候选选择期间战斗是否暂停，何时恢复？", _tag("three_choice"), severity="qa_blocking"),
        _slot("random_presentation", "presentation_only", ("presentation",), "presentation", "候选或抽取结果如何展示？", _any("candidate_ui", "roulette"), severity="documentation_gap"),
    ), ("flow", "pool", "draw", "refresh", "exceptions")),
    _schema("settlement", "结算", (
        _slot("settlement_trigger", "core", ("flow", "logic"), "flow", "哪些胜负事件会触发结算，触发后战斗在什么时点停止？"),
        _slot("result_determination", "core", ("logic",), "result", "结算结果依据哪些已确认状态判定？"),
        _slot("reward_rule", "conditional", ("logic", "config"), "reward", "奖励如何确定？", _tag("reward"), severity="implementation_blocking"),
        _slot("persistence_timing", "conditional", ("flow", "config"), "persistence", "何时落库？", _tag("persistence"), severity="implementation_blocking", gap_domain="technical"),
        _slot("exit_path", "core", ("flow", "interaction"), "exit", "玩家通过哪些操作离开结算，分别进入哪个后续状态？"),
        _slot("settlement_presentation", "presentation_only", ("presentation",), "presentation", "结算表现如何定义？", _tag("settlement_ui"), severity="documentation_gap"),
    ), ("flow", "result", "reward", "persistence", "exit", "presentation")),
    _schema("spawn", "刷新", (
        _slot("spawn_trigger", "core", ("logic", "flow"), "flow", "{object}刷新在什么条件下开始？", probe_type="LifecycleBoundaryProbe", target_property="first_appearance"),
        _slot("spawn_source", "core", ("logic", "config"), "definition", "{object}从哪些区域或点位生成？"),
        _slot("spawn_composition", "conditional", ("numeric", "config"), "definition", "每次刷新的{object}种类和数量如何确定？", _any("wave", "multiple_enemies"), severity="implementation_blocking"),
        _slot("spawn_interval", "conditional", ("numeric", "config"), "flow", "{object}连续刷新之间的时间间隔是多少？", _any("repeat", "continuous"), severity="implementation_blocking"),
        _slot("spawn_stop_condition", "core", ("logic", "flow"), "flow", "{object}刷新在什么条件下停止？"),
    ), ("definition", "flow")),
    _schema("level_flow", "关卡流程", (
        _slot("level_start_condition", "core", ("logic", "flow"), "flow", "关卡流程在什么条件下开始？"),
        _slot("stage_transition", "conditional", ("logic", "flow"), "flow", "当前关卡阶段满足哪些条件后切换，切换时保留或重置哪些战斗状态？", _any("stage", "countdown", "boss"), severity="implementation_blocking"),
        _slot("victory_condition", "core", ("logic", "flow"), "result", "满足什么条件时判定胜利？"),
        _slot("failure_condition", "core", ("logic", "flow"), "result", "满足什么条件时判定失败？"),
        _slot("level_end_timing", "core", ("logic", "flow"), "flow", "胜负条件成立后，战斗在什么时点停止并进入后续流程？"),
    ), ("flow", "result")),
)

_GENERIC = {
    "attribute": "基础属性", "damage_death": "受击及死亡", "unlock_progression": "解锁与养成",
    "state_machine": "状态", "combat_calculation": "战斗计算",
    "interaction": "交互", "presentation": "战斗表现",
    "content_catalog": "内容清单",
}
for _type, _title in _GENERIC.items():
    _BASE += (_schema(_type, _title, (_slot(f"{_type}_definition", "core", ("logic", "flow", "numeric", "config", "interaction", "presentation"), "core", f"{_title}的核心规则是什么？"),), ("core",)),)


class ChapterSchemaLibrary:
    def __init__(self) -> None:
        self._items = {item.schema_key: item for item in _BASE}
        for chapter_type, variant, extras in (
            ("randomization", "three_choice", (_slot("confirm_effect_timing", "conditional", ("interaction", "flow"), "flow", "玩家确认候选后，效果在什么时点生效，战斗在什么时点恢复？", _tag("three_choice"), severity="implementation_blocking"),)),
            ("randomization", "roulette", (_slot("roulette_stop", "conditional", ("logic", "flow"), "draw", "滚动在什么条件下停止，最终结果在什么时点确定？", _tag("roulette"), severity="implementation_blocking"),)),
            ("attack", "melee", ()), ("attack", "ranged", ()),
            ("movement", "follow", ()), ("movement", "straight_line", ()),
        ):
            base = self.resolve(chapter_type, None, SCHEMA_VERSION)
            item = replace(base, mechanic_variant=variant, slots=base.slots + extras, base_schema_key=base.schema_key)
            self._items[item.schema_key] = item

    def resolve(self, chapter_type: str, mechanic_variant: str | None, version: str) -> ChapterSchema:
        key = f"{version}:{chapter_type}:{mechanic_variant or 'base'}"
        if key not in self._items:
            if mechanic_variant and f"{version}:{chapter_type}:base" in self._items:
                raise KeyError(f"unregistered mechanic variant: {chapter_type}/{mechanic_variant}")
            raise KeyError(f"unregistered chapter schema: {key}")
        return self._items[key]

    def list_types(self, version: str) -> tuple[str, ...]:
        return tuple(sorted(item.chapter_type for item in self._items.values() if item.schema_version == version and item.mechanic_variant is None))

    def validate_all(self) -> tuple[str, ...]:
        errors = []
        for schema in self._items.values():
            for slot in schema.slots:
                if slot.applicability in {"core", "conditional"} and slot.gap_policy is None:
                    errors.append(f"{schema.schema_key}:{slot.slot_id}:gap_policy")
                if slot.applicability in {"conditional", "presentation_only"} and slot.applicable_when is None:
                    errors.append(f"{schema.schema_key}:{slot.slot_id}:predicate")
                if slot.applicability == "derived" and slot.derivation is None:
                    errors.append(f"{schema.schema_key}:{slot.slot_id}:derivation")
        return tuple(errors)


chapter_schema_library = ChapterSchemaLibrary()
