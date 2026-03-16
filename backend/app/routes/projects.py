from fastapi import APIRouter

from app.schemas.project import ProjectCreate, ProjectResponse, build_project_response
from app.services.project_service import create_project, list_projects

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=list[ProjectResponse])
def get_projects():
    projects = list_projects()
    return [build_project_response(project) for project in projects]


@router.post("/", response_model=ProjectResponse)
def create_project_route(payload: ProjectCreate):
    project = create_project(payload)
    return build_project_response(project)
