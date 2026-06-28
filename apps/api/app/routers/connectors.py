from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.integrations.job_providers import get_provider, list_provider_statuses
from app.models import User
from app.services.connector_runner import last_run, run_connector

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectorRunRequest(BaseModel):
    use_fixture: bool = False
    params: dict = Field(default_factory=dict)


@router.get("")
def list_connectors(_: User = Depends(get_current_user)) -> dict:
    statuses = []
    for status in list_provider_statuses():
        data = status.to_dict()
        run = last_run(status.provider_id)
        if run:
            data["last_run_at"] = run["last_run_at"].isoformat()
            data["last_job_count"] = run["last_job_count"]
            data["last_fixture"] = run["fixture"]
        statuses.append(data)
    return {"connectors": statuses}


@router.get("/{provider_id}")
def get_connector(provider_id: str, _: User = Depends(get_current_user)) -> dict:
    try:
        provider = get_provider(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    data = provider.base_status().to_dict()
    run = last_run(provider_id)
    if run:
        data["last_run_at"] = run["last_run_at"].isoformat()
        data["last_job_count"] = run["last_job_count"]
    return data


@router.post("/{provider_id}/run")
def run_connector_endpoint(
    provider_id: str,
    payload: ConnectorRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return run_connector(
            db,
            provider_id,
            actor=current_user.email,
            use_fixture=payload.use_fixture,
            params=payload.params,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
