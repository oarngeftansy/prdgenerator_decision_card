from backend.feishu_native_board import compile_gve16_whiteboard, compile_gve16_whiteboards, compile_reference_whiteboard


def test_compiler_emits_approved_native_whiteboard_contract():
    job = {
        "frames": [
            {"id": "F0001", "imagePath": "frames/F0001.jpg"},
            {"id": "F0002", "imagePath": "frames/F0002.jpg"},
        ],
        "planningModel": {
            "mode": "interaction",
            "loopHierarchy": {
                "largeLoops": [{
                    "title": "完成一次选择",
                    "repeatCondition": "关闭详情后可继续选择",
                    "stages": [{
                        "title": "功法选择",
                        "smallLoops": [{
                            "steps": [
                                {
                                    "title": "浏览功法",
                                    "userAction": "切换属性筛选",
                                    "systemResponse": "刷新可选功法",
                                    "evidence": [{"sourceId": "F0001"}],
                                },
                                {
                                    "title": "查看详情",
                                    "userAction": "长按功法卡片",
                                    "systemResponse": "打开功法详情",
                                    "evidence": [{"sourceId": "F0002"}],
                                },
                            ]
                        }],
                    }],
                }]
            },
        },
    }

    board = compile_gve16_whiteboard(job)

    sections = [node for node in board.structure["nodes"] if node["type"] == "section"]
    assert len(sections) == 2
    assert all(node["locked"] is False and node["children"] for node in sections)
    assert any(node["id"].startswith("page-title-") for node in board.structure["nodes"])
    assert any(node["id"].startswith("page-copy-") for node in board.structure["nodes"])
    assert [image.frame_id for image in board.images] == ["F0001", "F0002"]
    assert all(image.node["type"] == "image" for image in board.images)
    markers = [node for node in board.overlay["nodes"] if node.get("composite_shape", {}).get("type") == "ellipse"]
    assert markers == []
    assert [node for node in board.overlay["nodes"] if node["type"] == "connector"] == []
    assert all(node["connector"]["shape"] == "straight" for node in board.overlay["nodes"] if node["type"] == "connector")
    assert all(not node["connector"].get("turning_points") for node in board.overlay["nodes"] if node["type"] == "connector")
    assert any(node.get("text", {}).get("text") for node in board.structure["nodes"] if node["id"].startswith("page-title-"))


def test_compiler_emits_planning_and_ordered_competitor_assets_only():
    job = {
        "frames": [{"id": "F0001", "imagePath": "frames/F0001.jpg"}],
        "planningModel": {"mode": "interaction", "events": [{"action": "打开", "response": "展示", "evidence": [{"sourceId": "F0001"}]}]},
        "reviewModel": {"referenceBoards": {
            "ux": "damaged legacy board",
            "competitor": {"assets": [
                {"id": "CPA-002", "sourceName": "second.png", "relativePath": "reference_boards/competitor/second.png", "order": 2, "status": "ready"},
                {"id": "CPA-001", "sourceName": "first.png", "relativePath": "reference_boards/competitor/first.png", "order": 1, "status": "ready"},
            ]},
        }},
    }

    boards = compile_gve16_whiteboards(job)
    (planning,) = boards

    assert [(item.key, item.title) for item in boards] == [("planning", "策划草图")]
    assert [image.image_path for image in planning.board.images] == ["frames/F0001.jpg"]


def test_gameplay_compiler_preserves_pre_migration_three_board_order():
    job = {
        "planningModel": {"mode": "gameplay", "events": []},
        "reviewModel": {"referenceBoards": {
            "ux": {"assets": []},
            "competitor": {"assets": []},
        }},
    }

    boards = compile_gve16_whiteboards(job)

    assert [(board.key, board.title) for board in boards] == [("planning", "策划草图")]


def test_competitor_board_rejects_noncanonical_or_missing_assets_and_keeps_ready_assets(tmp_path):
    reference_dir = tmp_path / "reference_boards" / "competitor"
    reference_dir.mkdir(parents=True)
    (reference_dir / "ready.png").write_bytes(b"ready")
    job = {
        "planningModel": {"mode": "interaction", "events": []},
        "reviewModel": {"referenceBoards": {"ux": ["damaged legacy board"], "competitor": {"assets": [
            {"id": "CPA-001", "relativePath": "reference_boards/competitor/ready.png", "sourceName": "ready", "order": 1, "status": "ready"},
            {"id": "CPA-002", "relativePath": "C:/outside.png", "sourceName": "absolute", "order": 2, "status": "ready"},
            {"id": "CPA-003", "relativePath": "reference_boards/competitor/../secret.png", "sourceName": "traversal", "order": 3, "status": "ready"},
            {"id": "CPA-004", "relativePath": "reference_boards/ux/wrong-board.png", "sourceName": "wrong-board", "order": 4, "status": "ready"},
            {"id": "CPA-005", "relativePath": "reference_boards/competitor/missing.png", "sourceName": "missing", "order": 5, "status": "missing"},
            {"id": "CPA-006", "relativePath": "reference_boards/competitor/not-on-disk.png", "sourceName": "deleted", "order": 6, "status": "ready"},
            {"id": "CPA-007", "relativePath": "\\\\server\\share.png", "sourceName": "unc", "order": 7, "status": "ready"},
            {"id": "CPA-008", "relativePath": "reference_boards\\competitor\\backslash.png", "sourceName": "backslash", "order": 8, "status": "ready"},
            {"id": "CPA-009", "relativePath": "reference_boards/competitor/./dot.png", "sourceName": "dot", "order": 9, "status": "ready"},
            {"id": "CPA-010", "relativePath": "reference_boards//competitor/repeated.png", "sourceName": "repeat", "order": 10, "status": "ready"},
        ]}}},
    }

    competitor = compile_reference_whiteboard(job, "competitor", "竞品参考", tmp_path)

    assert [image.image_path for image in competitor.images] == ["reference_boards/competitor/ready.png"]
    assert any(node.get("style", {}).get("fill_color") == "#fff3bf" and node["text"]["text"] == "素材缺失/待补充" for node in competitor.overlay["nodes"])


def test_empty_competitor_board_has_only_a_yellow_pending_note():
    job = {"planningModel": {"mode": "interaction", "events": []}, "reviewModel": {"referenceBoards": {
        "ux": {"assets": [{"id": "UXA-001"}]},
        "competitor": {"assets": []},
    }}}

    competitor = compile_reference_whiteboard(job, "competitor", "竞品参考")

    assert competitor.images == ()
    assert any(node.get("style", {}).get("fill_color") == "#fff3bf" and node["text"]["text"] == "待补充" for node in competitor.overlay["nodes"])


def test_explicit_missing_or_file_job_dir_marks_ready_reference_assets_pending(tmp_path):
    job = {"planningModel": {"mode": "interaction", "events": []}, "reviewModel": {"referenceBoards": {
        "ux": {"assets": [{"id": "UXA-001"}]},
        "competitor": {"assets": [{"id": "CPA-001", "relativePath": "reference_boards/competitor/ready.png", "order": 1, "status": "ready"}]},
    }}}
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("file")

    for job_dir in (tmp_path / "missing-directory", file_path):
        competitor = compile_reference_whiteboard(job, "competitor", "竞品参考", job_dir)
        assert competitor.images == ()
        assert any(node.get("text", {}).get("text") == "待补充" for node in competitor.overlay["nodes"])


def test_reference_board_requires_complete_unique_asset_metadata_before_rendering():
    job = {"planningModel": {"mode": "interaction", "events": []}, "reviewModel": {"referenceBoards": {
        "ux": {"assets": [{"id": "UXA-001"}]}, "competitor": {"assets": [
            {"id": "CPA-001", "relativePath": "reference_boards/competitor/valid.png", "order": 1, "status": "ready"},
            {"id": "", "relativePath": "reference_boards/competitor/no-id.png", "order": 2, "status": "ready"},
            {"id": "CPA-003", "relativePath": "reference_boards/competitor/no-order.png", "order": 0, "status": "ready"},
            {"id": "CPA-004", "relativePath": "reference_boards/competitor/C:.png", "order": 4, "status": "ready"},
            {"id": "CPA-005", "relativePath": "reference_boards/competitor/duplicate-a.png", "order": 5, "status": "ready"},
            {"id": "CPA-005", "relativePath": "reference_boards/competitor/duplicate-b.png", "order": 6, "status": "ready"},
            {"id": "CPA-007", "relativePath": "reference_boards/competitor/duplicate-order-a.png", "order": 7, "status": "ready"},
            {"id": "CPA-008", "relativePath": "reference_boards/competitor/duplicate-order-b.png", "order": 7, "status": "ready"},
            {"id": "CPA-009", "relativePath": "reference_boards/competitor/duplicate-path.png", "order": 9, "status": "ready"},
            {"id": "CPA-010", "relativePath": "reference_boards/competitor/duplicate-path.png", "order": 10, "status": "ready"},
        ]},
    }}}

    competitor = compile_reference_whiteboard(job, "competitor", "竞品参考")

    assert [image.frame_id for image in competitor.images] == ["CPA-001"]
    assert any(node.get("text", {}).get("text") == "素材缺失/待补充" for node in competitor.overlay["nodes"])
