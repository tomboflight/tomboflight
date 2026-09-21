from __future__ import annotations

import runpy
from pathlib import Path


APPLICATOR = Path(__file__).with_name("apply_step6_logout_revocation.py")
namespace = runpy.run_path(str(APPLICATOR), run_name="step6_logout_applicator")

broken = 'return "\n".join('
fixed = 'return "\\n".join('
test_content = str(namespace.get("TEST_CONTENT") or "")
if test_content.count(broken) != 1:
    raise RuntimeError("Unable to locate the generated newline-join test source.")
namespace["TEST_CONTENT"] = test_content.replace(broken, fixed, 1)
namespace["main"]()
