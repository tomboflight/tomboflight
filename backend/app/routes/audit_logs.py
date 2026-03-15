from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.audit_log import AuditLogResponse, build_audit_log_response
from app.services.audit_log_service import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=list[AuditLogResponse])
def get_audit_logs(current_user: dict = Depends(require_admin)):
    logs = list_audit_logs()
    return [build_audit_log_response(log) for log in logs]