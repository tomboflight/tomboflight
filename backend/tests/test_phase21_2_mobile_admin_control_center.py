from pathlib import Path
from unittest import TestCase


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REVISION = "20260828-phase21-2"


class Phase212MobileAdminControlCenterContractTests(TestCase):
    def test_control_center_loads_scoped_mobile_assets_and_disclosure(self):
        html = (REPOSITORY_ROOT / "admin-control-center.html").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            f"admin-control-center-mobile.css?v={REVISION}",
            html,
        )
        self.assertIn(
            f"admin-control-center-mobile.js?v={REVISION}",
            html,
        )
        self.assertIn('data-mobile-nav="collapsed"', html)
        self.assertIn("data-admin-rail-toggle", html)
        self.assertIn('aria-controls="admin-operations-navigation"', html)
        self.assertIn('id="admin-operations-navigation"', html)

    def test_mobile_layout_removes_sticky_rail_and_desktop_columns(self):
        styles = (
            REPOSITORY_ROOT / "admin-control-center-mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 1180px)", styles)
        self.assertIn("position: static", styles)
        self.assertIn('[data-mobile-nav="collapsed"] .admin-case-nav', styles)
        self.assertIn("display: none", styles)
        self.assertIn("@media (max-width: 1024px)", styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", styles)
        self.assertIn("min-height: 44px", styles)
        self.assertIn("flex-direction: column", styles)

    def test_mobile_navigation_collapses_after_queue_selection(self):
        script = (
            REPOSITORY_ROOT / "admin-control-center-mobile.js"
        ).read_text(encoding="utf-8")

        self.assertIn('MOBILE_CONTROL_CENTER = "(max-width: 1180px)"', script)
        self.assertIn('target.closest("[data-case-queue]")', script)
        self.assertIn('navigation.querySelectorAll("details[open]")', script)
        self.assertIn("setExpanded(false)", script)
        self.assertIn('navigation.setAttribute("aria-hidden"', script)
        self.assertIn("caseCenter.scrollIntoView", script)
