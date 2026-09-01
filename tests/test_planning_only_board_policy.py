from backend.feishu_native_board import (
    compile_accepted_delivery_whiteboards,
    compile_gve16_delivery_whiteboards,
    compile_gve16_whiteboards,
)
from backend.review_service import confirm_flow, confirm_stage
from backend.review_model import build_review_model, empty_rule_domains
from tests.review_fixtures import make_image_job


def test_all_native_board_compilers_emit_planning_board_only():
    job = {
        "planningModel": {"mode": "gameplay", "events": []},
        "reviewModel": {"referenceBoards": {"ux": {"assets": []}, "competitor": {"assets": []}}},
    }
    for boards in (
        compile_gve16_delivery_whiteboards(job),
        compile_gve16_whiteboards(job),
        compile_accepted_delivery_whiteboards(job),
    ):
        assert [(board.key, board.title) for board in boards] == [("planning", "策划草图")]


def test_last_interaction_stage_skips_ue_flow_gate():
    model = build_review_model(make_image_job())
    model["ruleDomains"] = empty_rule_domains()
    model["ruleDomains"].update(
        reviewedDomains=["narrative", "guidance", "redDots"],
        confirmation={"confirmed": True, "revision": model["revision"]},
    )
    model = confirm_flow(model, model["revision"])
    for stage in model["stages"]:
        model = confirm_stage(model, stage["id"], model["revision"])
    assert model["reviewState"]["status"] == "preview_pending"
    assert "ueFlowConfirmed" not in model["reviewState"]
    assert "ueFlowFingerprint" not in model["reviewState"]
