from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LineageCertificateFamily(BaseModel):
    id: str
    family_name: str
    project_id: Optional[str] = None
    status: Optional[str] = None
    created_by: Optional[str] = None


class LineageCertificateSummary(BaseModel):
    member_count: int = 0
    relationship_count: int = 0
    verification_record_count: int = 0
    verified_member_count: int = 0
    verification_pass_count: int = 0
    generation_count: int = 0


class LineageCertificateMember(BaseModel):
    id: str
    full_name: str
    role: Optional[str] = None
    relationship_type: Optional[str] = None
    generation: Optional[int] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    is_verified: bool = False
    canonical_person_id: Optional[str] = None


class LineageCertificateRelationship(BaseModel):
    id: str
    person_1_id: Optional[str] = None
    person_2_id: Optional[str] = None
    relationship_type: Optional[str] = None
    status: Optional[str] = None


class LineageCertificateVerificationRecord(BaseModel):
    id: str
    verification_type: Optional[str] = None
    status: Optional[str] = None
    reviewed_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LineageCertificateExecutive(BaseModel):
    record_integrity: str = "Recorded"
    founding_line: str = "Founding lineage not available."
    verified_branches: str = "Branch summary not available."
    key_lineage_path: List[str] = Field(default_factory=list)
    descendant_summary: str = "No descendant records summarized on this certificate."


class LineageCertificatePayload(BaseModel):
    certificate_type: str = "lineage_certificate"
    certificate_version: str = "1.0.0"
    issued_at: str

    certificate_id: str
    status: str
    integrity_hash: str

    family: LineageCertificateFamily
    summary: LineageCertificateSummary

    executive: LineageCertificateExecutive = Field(default_factory=LineageCertificateExecutive)

    members: List[LineageCertificateMember] = Field(default_factory=list)
    relationships: List[LineageCertificateRelationship] = Field(default_factory=list)
    verification_records: List[LineageCertificateVerificationRecord] = Field(default_factory=list)

    # optional extra metadata if you want it later
    meta: Dict[str, Any] = Field(default_factory=dict)


class LineageCertificateResponse(BaseModel):
    success: bool = True
    certificate: LineageCertificatePayload