"""Scripting engine endpoints.

Tenants can create, validate, and execute DCS Script automations
for custom compliance checks, workflow rules, and data processing.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.engines.scripting import ScriptContext, ScriptError, ScriptInterpreter, validate_script
from dcs_api.models.customization import (
    Script,
    ScriptExecution,
    ScriptType,
    TriggerEvent,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.customization import (
    ScriptCreate,
    ScriptExecutionResponse,
    ScriptResponse,
    ScriptRunRequest,
    ScriptUpdate,
    ScriptValidateRequest,
)

router = APIRouter()

MAX_PAGE_SIZE = 100

# Entity names → loader functions that pull data for scripts
ENTITY_LOADERS: dict[str, Any] = {}


async def _load_entity_data(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity: str,
    limit: int = 10000,
) -> list[dict]:
    """Load entity data as list-of-dicts for use in scripts."""
    from dcs_api.engines.reporting import ENTITY_MODEL_MAP, _model_to_dict

    model = ENTITY_MODEL_MAP.get(entity)
    if not model:
        return []

    query = select(model)
    if hasattr(model, "tenant_id"):
        query = query.where(model.tenant_id == tenant_id)
    query = query.limit(limit)

    result = await session.execute(query)
    rows = result.scalars().all()
    return [_model_to_dict(r) for r in rows]


@router.get("", response_model=PaginatedResponse[ScriptResponse])
async def list_scripts(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    script_type: str | None = None,
    jurisdiction: str | None = None,
    trigger_event: str | None = None,
) -> PaginatedResponse[ScriptResponse]:
    query = select(Script).where(Script.tenant_id == user.tenant_id)

    if script_type:
        query = query.where(Script.script_type == script_type)
    if jurisdiction:
        query = query.where(Script.jurisdiction == jurisdiction.upper())
    if trigger_event:
        query = query.where(Script.trigger_event == trigger_event)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(Script.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    scripts = list(result.scalars().all())

    return PaginatedResponse(
        items=[ScriptResponse.model_validate(s) for s in scripts],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ScriptResponse:
    query = select(Script).where(
        Script.id == script_id, Script.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not found")
    return ScriptResponse.model_validate(script)


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    data: ScriptCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.CONFIGURE_INTEGRATIONS))],
) -> ScriptResponse:
    """Create a new script. Code is validated before saving."""
    errors = validate_script(data.code)
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": errors},
        )

    script = Script(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        script_type=ScriptType(data.script_type),
        code=data.code,
        trigger_event=TriggerEvent(data.trigger_event) if data.trigger_event else None,
        trigger_config=data.trigger_config,
        parameters=[p.model_dump() for p in data.parameters],
        jurisdiction=data.jurisdiction.upper() if data.jurisdiction else None,
        created_by=user.user_id,
    )
    session.add(script)
    await session.flush()
    return ScriptResponse.model_validate(script)


@router.patch("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: uuid.UUID,
    data: ScriptUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.CONFIGURE_INTEGRATIONS))],
) -> ScriptResponse:
    query = select(Script).where(
        Script.id == script_id, Script.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not found")
    if script.is_system:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot modify system scripts")

    if data.code is not None:
        errors = validate_script(data.code)
        if errors:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"validation_errors": errors},
            )
        script.version += 1

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "parameters" and isinstance(value, list):
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(script, key, value)

    await session.flush()
    return ScriptResponse.model_validate(script)


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(
    script_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.CONFIGURE_INTEGRATIONS))],
) -> None:
    query = select(Script).where(
        Script.id == script_id, Script.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not found")
    if script.is_system:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete system scripts")
    await session.delete(script)


@router.post("/validate")
async def validate_script_code(
    data: ScriptValidateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Validate DCS Script code without executing it."""
    errors = validate_script(data.code)
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "line_count": len(data.code.strip().splitlines()),
    }


@router.post("/{script_id}/run")
async def run_script(
    script_id: uuid.UUID,
    run_request: ScriptRunRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.CONFIGURE_INTEGRATIONS))],
) -> dict:
    """Execute a saved script with optional parameters."""
    query = select(Script).where(
        Script.id == script_id, Script.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not found")
    if not script.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Script is inactive")

    now = datetime.now(timezone.utc)
    execution = ScriptExecution(
        tenant_id=user.tenant_id,
        script_id=script.id,
        script_version=script.version,
        parameters=run_request.parameters,
        status="running",
        executed_by=user.user_id,
        started_at=now,
    )
    session.add(execution)
    await session.flush()

    try:
        # Load entity data that the script can query
        data: dict[str, list[dict]] = {}
        for entity_name in ["accounts", "consumers", "payments", "disputes"]:
            data[entity_name] = await _load_entity_data(session, user.tenant_id, entity_name)

        ctx = ScriptContext(
            tenant_id=user.tenant_id,
            parameters=run_request.parameters,
            data=data,
            jurisdiction=script.jurisdiction,
            dry_run=run_request.dry_run,
        )

        interpreter = ScriptInterpreter(ctx)
        script_result = interpreter.execute(script.code)

        end = datetime.now(timezone.utc)
        execution.status = "completed"
        execution.result = script_result
        execution.rows_affected = script_result.get("rows_affected", 0)
        execution.duration_ms = int((end - now).total_seconds() * 1000)
        execution.completed_at = end

        script.last_run_at = end
        script.last_run_status = "completed"
        script.last_run_result = {
            "rows_affected": script_result.get("rows_affected", 0),
            "flag_count": len(script_result.get("flags", [])),
        }

        return {
            "execution_id": str(execution.id),
            "script_name": script.name,
            "dry_run": run_request.dry_run,
            **script_result,
        }

    except ScriptError as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.completed_at = datetime.now(timezone.utc)
        script.last_run_at = execution.completed_at
        script.last_run_status = "failed"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.completed_at = datetime.now(timezone.utc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Script execution error")


@router.get("/{script_id}/executions", response_model=list[ScriptExecutionResponse])
async def list_script_executions(
    script_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    limit: int = Query(20, ge=1, le=100),
) -> list[ScriptExecutionResponse]:
    query = (
        select(ScriptExecution)
        .where(
            ScriptExecution.script_id == script_id,
            ScriptExecution.tenant_id == user.tenant_id,
        )
        .order_by(ScriptExecution.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return [ScriptExecutionResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/builtins/functions")
async def list_builtin_functions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict]:
    """List available built-in functions for DCS Script."""
    return [
        {"name": "days_since", "args": ["date"], "description": "Days between a date and today"},
        {"name": "days_until", "args": ["date"], "description": "Days between today and a future date"},
        {"name": "sol_years", "args": ["jurisdiction"], "description": "Statute of limitations years for a state"},
        {"name": "abs", "args": ["number"], "description": "Absolute value"},
        {"name": "round", "args": ["number", "places"], "description": "Round to N decimal places"},
        {"name": "upper", "args": ["string"], "description": "Convert to uppercase"},
        {"name": "lower", "args": ["string"], "description": "Convert to lowercase"},
        {"name": "len", "args": ["collection"], "description": "Length of list or string"},
        {"name": "now", "args": [], "description": "Current UTC datetime"},
        {"name": "today", "args": [], "description": "Current UTC date"},
        {"name": "format_currency", "args": ["cents"], "description": "Format cents as $X,XXX.XX"},
        {"name": "min", "args": ["a", "b"], "description": "Minimum of two values"},
        {"name": "max", "args": ["a", "b"], "description": "Maximum of two values"},
        {"name": "str", "args": ["value"], "description": "Convert to string"},
        {"name": "int", "args": ["value"], "description": "Convert to integer"},
        {"name": "float", "args": ["value"], "description": "Convert to float"},
    ]


@router.get("/builtins/sol-years")
async def list_sol_years(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, int]:
    """List statute of limitations years by jurisdiction."""
    from dcs_api.engines.scripting import SOL_YEARS_MAP
    return SOL_YEARS_MAP
