from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.schemas.experience import (
    ExperienceChamberResponse,
    ExperienceMapResponse,
    ExperienceSessionResponse,
    ExperienceSessionStartRequest,
    ExperienceStoryResponse,
    ExperienceTransitionRequest,
    LineageChamberSummaryResponse,
    ModuleUnlock,
    RecommendedNextStepResponse,
)
from app.services.chamber_service import build_experience_chamber
from app.services.experience_state_service import (
    build_experience_map,
    get_experience_session,
    get_module_unlocks,
    get_recommended_next_step,
    list_experience_checkpoints,
    start_experience_session,
    transition_experience_session,
)
from app.services.lineage_chamber_service import build_lineage_chamber_summary
from app.services.narrative_service import build_experience_story
from app.services.workspace_access_service import resolve_workspace_context

router = APIRouter(tags=["Experience"])


@router.get("/experience/session", response_model=ExperienceSessionResponse)
def get_experience_session_route(
    project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return get_experience_session(current_user, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/experience/session/start", response_model=ExperienceSessionResponse)
def start_experience_session_route(
    payload: ExperienceSessionStartRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return start_experience_session(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/experience/session/transition", response_model=ExperienceSessionResponse)
def transition_experience_session_route(
    payload: ExperienceTransitionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return transition_experience_session(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/experience/map", response_model=ExperienceMapResponse)
def get_experience_map_route(
    project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return build_experience_map(current_user, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/experience/checkpoints")
def get_experience_checkpoints_route(
    project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return {"items": list_experience_checkpoints(current_user, project_id=project_id)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/experience/recommended-next-step",
    response_model=RecommendedNextStepResponse,
)
def get_recommended_next_step_route(
    project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return get_recommended_next_step(current_user, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/experience/module-unlocks", response_model=list[ModuleUnlock])
def get_module_unlocks_route(
    project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return get_module_unlocks(current_user, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/lineage-chamber/{family_id}/summary", response_model=LineageChamberSummaryResponse)
def get_lineage_chamber_summary_route(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    resolve_workspace_context(current_user, family_id=family_id)
    try:
        return build_lineage_chamber_summary(family_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/experience-story/family/{family_id}", response_model=ExperienceStoryResponse)
def get_experience_story_route(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    resolve_workspace_context(current_user, family_id=family_id)
    try:
        return build_experience_story(family_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/experience/chamber/{project_id}", response_model=ExperienceChamberResponse)
def get_experience_chamber_route(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return build_experience_chamber(current_user, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
