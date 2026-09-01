from pathlib import Path
import unittest


class SingleFrameUiContractTest(unittest.TestCase):
    def test_single_frame_ui_contract(self):
        css = Path("css/style.css").read_text(encoding="utf-8")
        html = Path("index.html").read_text(encoding="utf-8")
        self.assertIn(".frame-reviewer-body", css)
        self.assertIn("58fr", css)
        self.assertIn("42fr", css)
        self.assertIn("min-width:44px", css)
        self.assertIn("min-height:44px", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("grid-template-columns:1fr", css)
        self.assertNotIn('id="frameList" style=', html)
        self.assertIn(".frame-review-toolbar", css)
        self.assertIn("flex-wrap:wrap", css)
        self.assertIn("frame-reviewer.js?v=ux10", html)
        self.assertIn(".frame-supplement-action-button { min-height:44px; }", css)


if __name__ == "__main__":
    unittest.main()
