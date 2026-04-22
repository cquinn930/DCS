"""Custom report builder endpoints.

Tenants can create, save, and execute parameterised report templates
that pull data from any entity with custom columns, filters,
grouping, aggregations, and multi-format output.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.engines.reporting import execute_report
from dcs_api.models.customization import (
    OutputFormat,
    ReportEntity,
    ReportExecution,
    ReportTemplate,
    ReportType,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.customization import (
    ReportExecutionResponse,
    ReportRunRequest,
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportTemplateUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[ReportTemplateResponse])
async def list_report_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    entity: str | None = None,
    jurisdiction: str | None = None,
) -> PaginatedResponse[ReportTemplateResponse]:
    """List report templates available to the tenant."""
    query = select(ReportTemplate).where(ReportTemplate.tenant_id == user.tenant_id)

    if entity:
        query = query.where(ReportTemplate.entity == entity)
    if jurisdiction:
        query = query.where(ReportTemplate.jurisdiction == jurisdiction.upper())

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(ReportTemplate.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    templates = list(result.scalars().all())

    return PaginatedResponse(
        items=[ReportTemplateResponse.model_validate(t) for t in templates],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{template_id}", response_model=ReportTemplateResponse)
async def get_report_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ReportTemplateResponse:
    query = select(ReportTemplate).where(
        ReportTemplate.id == template_id, ReportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")
    return ReportTemplateResponse.model_validate(template)


@router.post("", response_model=ReportTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_report_template(
    data: ReportTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ReportTemplateResponse:
    template = ReportTemplate(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        report_type=ReportType(data.report_type),
        entity=ReportEntity(data.entity),
        columns=[c.model_dump() for c in data.columns],
        filters=[f.model_dump() for f in data.filters],
        grouping=data.grouping,
        aggregations=[a.model_dump() for a in data.aggregations],
        sort_order=[s.model_dump() for s in data.sort_order],
        parameters=[p.model_dump() for p in data.parameters],
        default_output_format=OutputFormat(data.default_output_format),
        allowed_output_formats=data.allowed_output_formats,
        jurisdiction=data.jurisdiction.upper() if data.jurisdiction else None,
        schedule_cron=data.schedule_cron,
        created_by=user.user_id,
    )
    session.add(template)
    await session.flush()
    return ReportTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=ReportTemplateResponse)
async def update_report_template(
    template_id: uuid.UUID,
    data: ReportTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ReportTemplateResponse:
    query = select(ReportTemplate).where(
        ReportTemplate.id == template_id, ReportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")
    if template.is_system:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot modify system templates")

    update_data = data.model_dump(exclude_unset=True)
    SERIALISE_FIELDS = {"columns", "filters", "aggregations", "sort_order", "parameters"}
    for key, value in update_data.items():
        if key in SERIALISE_FIELDS and isinstance(value, list):
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(template, key, value)

    await session.flush()
    return ReportTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> None:
    query = select(ReportTemplate).where(
        ReportTemplate.id == template_id, ReportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")
    if template.is_system:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete system templates")
    await session.delete(template)


@router.post("/{template_id}/run")
async def run_report(
    template_id: uuid.UUID,
    run_request: ReportRunRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Execute a report template and return results."""
    query = select(ReportTemplate).where(
        ReportTemplate.id == template_id, ReportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")

    now = datetime.now(timezone.utc)
    execution = ReportExecution(
        tenant_id=user.tenant_id,
        template_id=template.id,
        parameters=run_request.parameters,
        output_format=OutputFormat(run_request.output_format),
        status="running",
        executed_by=user.user_id,
        started_at=now,
    )
    session.add(execution)
    await session.flush()

    try:
        report_result = await execute_report(
            session=session,
            entity=template.entity.value,
            tenant_id=user.tenant_id,
            columns=template.columns,
            filters=template.filters,
            grouping=template.grouping,
            aggregations=template.aggregations,
            sort_order=template.sort_order,
            parameters=run_request.parameters,
            output_format=run_request.output_format,
            limit=run_request.limit,
        )
        execution.status = "completed"
        execution.row_count = report_result["row_count"]
        execution.completed_at = datetime.now(timezone.utc)

        return {
            "execution_id": str(execution.id),
            "template_name": template.name,
            **report_result,
        }
    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.completed_at = datetime.now(timezone.utc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{template_id}/executions", response_model=list[ReportExecutionResponse])
async def list_report_executions(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
) -> list[ReportExecutionResponse]:
    query = (
        select(ReportExecution)
        .where(
            ReportExecution.template_id == template_id,
            ReportExecution.tenant_id == user.tenant_id,
        )
        .order_by(ReportExecution.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return [ReportExecutionResponse.model_validate(e) for e in result.scalars().all()]
