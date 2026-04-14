import unittest
from pathlib import Path


class ViewerRenderingSafetyTests(unittest.TestCase):
    def test_viewer_script_uses_safe_dom_rendering_for_dynamic_lists(self):
        script_path = (
            Path(__file__).resolve().parents[2] / "viewer" / "js" / "script.js"
        )
        source = script_path.read_text(encoding="utf-8")

        self.assertNotIn("pathList.innerHTML", source)
        self.assertNotIn("branchOptions.innerHTML", source)
        self.assertIn("document.createElement(\"div\")", source)
        self.assertIn("document.createElement(\"button\")", source)
        self.assertIn("button.textContent = label", source)


if __name__ == "__main__":
    unittest.main()
