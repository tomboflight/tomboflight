from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BILLING_PAGE = REPOSITORY_ROOT / "billing.html"


def _billing_csp_directives() -> dict[str, set[str]]:
    html = BILLING_PAGE.read_text(encoding="utf-8")
    match = re.search(
        r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]+)"\s*/?>',
        html,
        flags=re.IGNORECASE,
    )
    assert match is not None, "billing.html must declare a Content-Security-Policy"

    directives: dict[str, set[str]] = {}
    for raw_directive in match.group(1).split(";"):
        parts = raw_directive.strip().split()
        if not parts:
            continue
        directives[parts[0]] = set(parts[1:])
    return directives


def test_billing_page_csp_allows_the_required_stripe_js_origins() -> None:
    html = BILLING_PAGE.read_text(encoding="utf-8")
    assert '<script src="https://js.stripe.com/v3/"></script>' in html

    directives = _billing_csp_directives()

    assert {
        "'self'",
        "https://js.stripe.com",
        "https://*.js.stripe.com",
    }.issubset(directives.get("script-src", set()))
    assert "https://api.stripe.com" in directives.get("connect-src", set())
    assert {
        "https://js.stripe.com",
        "https://*.js.stripe.com",
        "https://hooks.stripe.com",
    }.issubset(directives.get("frame-src", set()))


def test_billing_page_does_not_weaken_script_execution_policy() -> None:
    script_sources = _billing_csp_directives().get("script-src", set())

    assert "'unsafe-inline'" not in script_sources
    assert "'unsafe-eval'" not in script_sources
