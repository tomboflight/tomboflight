from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.consistency import ConsistencyReport
from app.services.consistency_service import run_consistency_check

router = APIRouter(prefix="/consistency", tags=["Consistency"])


@router.get("/report", response_model=ConsistencyReport)
def consistency_report(current_user: dict = Depends(require_admin)):
    issues = run_consistency_check()

    return {
        "issue_count": len(issues),
        "issues": issues,
    }