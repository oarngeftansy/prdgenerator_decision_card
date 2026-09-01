import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FeishuPublishUiContractTest(unittest.TestCase):
    def test_publication_control_is_accessible_and_has_safe_touch_targets(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="feishuPublication"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('src="js/feishu-publish.js?v=ux16"', html)
        self.assertNotIn('id="feishuToken"', html)
        self.assertIn(".feishu-publication .btn", css)
        self.assertIn("min-height:44px", css.replace(" ", ""))

    def test_site_exposes_one_combined_interaction_and_gameplay_workflow(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        backend = (ROOT / "js" / "backend.js").read_text(encoding="utf-8")

        self.assertIn("移动端交互与玩法策划案", html)
        self.assertIn("交互与玩法审核工作台", html)
        self.assertIn("导出完整飞书策划案", html)
        self.assertIn("审核交互流程 → 审核玩法章节", html)
        self.assertIn('id="projectType" type="hidden" value="interaction"', html)
        self.assertNotIn('option value="gameplay"', html)
        self.assertNotIn('option value="interaction"', html)
        self.assertIn('<option selected>Mobile Web</option>', html)
        self.assertIn(".secondary-exit", css)
        self.assertIn(".locked-field", css)
        self.assertIn(".standard-library", css)
        self.assertIn('state.analysisMode = "interaction"', app)
        self.assertIn('"完整交互与玩法策划案"', app)
        self.assertIn('data.append("mode", "interaction")', backend)

        feishu = (ROOT / "js" / "feishu-publish.js").read_text(encoding="utf-8")
        self.assertIn("选择飞书保存位置", feishu)
        self.assertIn("保存位置：", feishu)
        self.assertNotIn("交互策划案和 UE 画板已经自动生成", feishu)

    def test_first_run_api_collection_can_be_saved_for_later_visits(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        config = (ROOT / "js" / "config.js").read_text(encoding="utf-8")

        self.assertIn('id="apiConfigPanel"', html)
        self.assertIn('id="apiConfigNotice"', html)
        self.assertIn('localStorage.setItem("vpr_api_key"', config)
        self.assertIn('localStorage.getItem("vpr_api_key")', config)
        self.assertIn('renderApiConfigGate', config)

    def test_guest_share_mode_hides_history_and_requires_own_api_key(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        config = (ROOT / "js" / "config.js").read_text(encoding="utf-8")
        app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="historyPanel" hidden', html)
        self.assertIn("首次进入请填写视觉模型 API", config)
        self.assertNotIn("已内置模型 API，可直接测试", config)
        self.assertNotIn("loadBuiltInApiConfig", app)


if __name__ == "__main__":
    unittest.main()
