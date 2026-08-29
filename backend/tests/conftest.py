"""Pytest bootstrap for local test execution.

Ensures tests run from repository root without extra env vars and
adds compatibility for Python versions that do not expose datetime.UTC.
"""

from __future__ import annotations

import datetime as _datetime
import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "ADMIN_IDENTITY_REGISTRY_JSON",
    json.dumps(
        {
            "active_officers": [
                {
                    "email": "ceo-admin@example.com",
                    "role_codes": ["ceo_master_admin", "executive_tech_admin"],
                    "profile": {
                        "full_name": "Test CEO",
                        "business_title": "CEO",
                        "access_tier": "ceo_master_admin",
                        "department_role": "executive_tech_admin",
                    },
                },
                {
                    "email": "finance-admin@example.com",
                    "role_codes": ["finance_admin"],
                    "profile": {
                        "full_name": "Test Finance Officer",
                        "business_title": "CFO",
                        "access_tier": "finance_admin",
                        "department_role": "finance_admin",
                    },
                },
                {
                    "email": "operations-admin@example.com",
                    "role_codes": ["operations_admin"],
                    "profile": {
                        "full_name": "Test Operations Officer",
                        "business_title": "COO",
                        "access_tier": "operations_admin",
                        "department_role": "operations_admin",
                    },
                },
            ],
            "retired_officers": [
                {
                    "email": "retired-officer@example.com",
                    "profile": {
                        "full_name": "Test Retired Officer",
                        "former_business_title": "CMO",
                        "retirement_reason": "Officer separation",
                    },
                }
            ],
        }
    ),
)
os.environ.setdefault(
    "ACCOUNT_SEPARATION_AUDIT_TARGETS_JSON",
    json.dumps(
        {
            "genesis": {
                "email": "genesis@example.com",
                "project_name": "Test Genesis Prototype",
                "package_code": "household_foundation",
                "family_name": "Example Family",
            },
            "personal_accounts": {
                "portrait-customer@example.com": {
                    "full_name": "Test Portrait Customer",
                    "account_type": "customer",
                },
                "legacy-customer@example.com": {
                    "full_name": "Test Legacy Customer",
                    "account_type": "customer",
                },
            },
            "target_personal_account_experience": {
                "portrait-customer@example.com": {
                    "package_code": "digital_legacy_portrait",
                    "project_name": "Test Portrait Experience",
                    "wallet_address": "0x1111111111111111111111111111111111111111",
                },
                "legacy-customer@example.com": {
                    "package_code": "legacy_plus",
                    "project_name": "Test Legacy Plus Experience",
                    "wallet_address": "0x3333333333333333333333333333333333333333",
                },
            },
        }
    ),
)

# Make `backend/app` importable as top-level `app` when running:
#   pytest backend/tests/... 
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Python <3.11 compatibility for code that imports `from datetime import UTC`.
if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc
