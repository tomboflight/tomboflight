import unittest
from pathlib import Path


VIEWER_ASSET_CACHE_TAG = "20260518-public-demo-refresh"


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

    def test_viewer_script_has_no_embedded_demo_or_prototype_family_dataset(self):
        script_path = (
            Path(__file__).resolve().parents[2] / "viewer" / "js" / "script.js"
        )
        source = script_path.read_text(encoding="utf-8")

        self.assertNotIn("const MORELAND_DEMO_MANIFEST", source)
        self.assertNotIn('mode: "demo"', source)
        self.assertNotIn("Genesis Prototype", source)
        self.assertNotIn("Moreland", source)
        self.assertNotIn("Selah Carter", source)
        self.assertIn(
            'selectedManifest = resolvePublicDemoManifest(DEMO_KEY) || UNAVAILABLE_MANIFEST;',
            source,
        )
        self.assertIn("autoAdvanceStateIds", source)
        self.assertIn('const DEFAULT_PUBLIC_DEMO_KEY = "malik-moreland";', source)
        self.assertIn("const DEMO_MODE = DEMO_KEY === DEFAULT_PUBLIC_DEMO_KEY;", source)
        self.assertIn('selectedManifest = liveManifest || UNAVAILABLE_MANIFEST;', source)

    def test_viewer_script_uses_production_safe_unavailable_copy(self):
        script_path = (
            Path(__file__).resolve().parents[2] / "viewer" / "js" / "script.js"
        )
        source = script_path.read_text(encoding="utf-8")

        self.assertIn(
            "No approved viewer manifest is available for this project yet.",
            source,
        )


    def test_viewer_demo_route_resolves_public_manifest(self):
        html_path = Path(__file__).resolve().parents[2] / "viewer" / "index.html"
        script_path = Path(__file__).resolve().parents[2] / "viewer" / "js" / "script.js"

        html = html_path.read_text(encoding="utf-8")
        source = script_path.read_text(encoding="utf-8")

        self.assertIn('const demoParam = String(params.get("demo") || "").trim().toLowerCase();', html)
        self.assertIn(
            'const isPreviewParam = params.get("preview") === "1" || demoParam === "malik-moreland";',
            html,
        )
        self.assertIn(f'css/style.css?v={VIEWER_ASSET_CACHE_TAG}', html)
        self.assertIn(f'../config.js?v={VIEWER_ASSET_CACHE_TAG}', html)
        self.assertIn(f'../app.js?v={VIEWER_ASSET_CACHE_TAG}', html)
        self.assertIn(f'js/genesis-prototype-manifest.js?v={VIEWER_ASSET_CACHE_TAG}', html)
        self.assertIn(f'js/script.js?v={VIEWER_ASSET_CACHE_TAG}', html)

        self.assertIn('const DEFAULT_PUBLIC_DEMO_KEY = "malik-moreland";', source)
        self.assertIn('const DEMO_MODE = DEMO_KEY === DEFAULT_PUBLIC_DEMO_KEY;', source)
        self.assertIn('if (DEMO_MODE) {', source)
        self.assertIn(
            'selectedManifest = resolvePublicDemoManifest(DEMO_KEY) || UNAVAILABLE_MANIFEST;',
            source,
        )
        self.assertIn('selectedManifest = liveManifest || UNAVAILABLE_MANIFEST;', source)


if __name__ == "__main__":
    unittest.main()
