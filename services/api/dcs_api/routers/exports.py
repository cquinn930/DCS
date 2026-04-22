"""Export engine endpoints.

Tenants define outbound export templates per client / jurisdiction
with column mappings, formatting, and optional scheduling.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.engines.exporting import execute_export
from dcs_api.models.customization import (
    ExportEntity,
    ExportFormat,
    ExportJob,
    ExportTemplate,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.customization import (
    ExportJobResponse,
    ExportRunRequest,
    ExportTemplateCreate,
    ExportTemplateResponse,
    ExportTemplateUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("/templates", response_model=PaginatedResponse[ExportTemplateResponse])
async def list_export_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    entity: str | None = None,
    client_name: str | None = None,
    jurisdiction: str | None = None,
) -> PaginatedResponse[ExportTemplateResponse]:
    query = select(ExportTemplate).where(ExportTemplate.tenant_id == user.tenant_id)

    if entity:
        query = query.where(ExportTemplate.entity == entity)
    if client_name:
        query = query.where(ExportTemplate.client_name == client_name)
    if jurisdiction:
        query = query.where(ExportTemplate.jurisdiction == jurisdiction.upper())

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(ExportTemplate.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    templates = list(result.scalars().all())

    return PaginatedResponse(
        items=[ExportTemplateResponse.model_validate(t) for t in templates],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/templates/{template_id}", response_model=ExportTemplateResponse)
async def get_export_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ExportTemplateResponse:
    query = select(ExportTemplate).where(
        ExportTemplate.id == template_id, ExportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export template not found")
    return ExportTemplateResponse.model_validate(template)


@router.post("/templates", response_model=ExportTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_export_template(
    data: ExportTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ExportTemplateResponse:
    template = ExportTemplate(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        target_format=ExportFormat(data.target_format),
        entity=ExportEntity(data.entity),
        columns=[c.model_dump() for c in data.columns],
        filters=[f.model_dump() for f in data.filters],
        sort_order=[s.model_dump() for s in data.sort_order],
        transformations=data.transformations,
        delimiter=data.delimiter,
        encoding=data.encoding,
        include_header=data.include_header,
        fixed_width_spec=data.fixed_width_spec,
        schedule_cron=data.schedule_cron,
        recipient_email=data.recipient_email,
        client_name=data.client_name,
        jurisdiction=data.jurisdiction.upper() if data.jurisdiction else None,
        created_by=user.user_id,
    )
    session.add(template)
    await session.flush()
    return ExportTemplateResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=ExportTemplateResponse)
async def update_export_template(
    template_id: uuid.UUID,
    data: ExportTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ExportTemplateResponse:
    query = select(ExportTemplate).where(
        ExportTemplate.id == template_id, ExportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export template not found")

    update_data = data.model_dump(exclude_unset=True)
    SERIALISE_FIELDS = {"columns", "filters", "sort_order"}
    for key, value in update_data.items():
        if key in SERIALISE_FIELDS and isinstance(value, list):
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(template, key, value)

    await session.flush()
    return ExportTemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> None:
    query = select(ExportTemplate).where(
        ExportTemplate.id == template_id, ExportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export template not found")
    await session.delete(template)


@router.post("/templates/{template_id}/run")
async def run_export(
    template_id: uuid.UUID,
    run_request: ExportRunRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> dict:
    """Execute an export template and return the output."""
    query = select(ExportTemplate).where(
        ExportTemplate.id == template_id, ExportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export template not found")

    now = datetime.now(timezone.utc)
    job = ExportJob(
        tenant_id=user.tenant_id,
        template_id=template.id,
        status="running",
        started_at=now,
        created_by=user.user_id,
    )
    session.add(job)
    await session.flush()

    try:
        export_result = await execute_export(
            session=session,
            tenant_id=user.tenant_id,
            entity=template.entity.value,
            columns=template.columns,
            filters=template.filters,
            sort_order=template.sort_order,
            transformations=template.transformations,
            target_format=template.target_format.value,
            delimiter=template.delimiter,
            include_header=template.include_header,
            fixed_width_spec=template.fixed_width_spec,
            parameters=run_request.parameters,
        )
        job.status = "completed"
        job.row_count = export_result["row_count"]
        job.completed_at = datetime.now(timezone.utc)

        return {
            "job_id": str(job.id),
            "template_name": template.name,
            **export_result,
        }
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.now(timezone.utc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/jobs", response_model=PaginatedResponse[ExportJobResponse])
async def list_export_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: str | None = None,
) -> PaginatedResponse[ExportJobResponse]:
    query = select(ExportJob).where(ExportJob.tenant_id == user.tenant_id)
    if status_filter:
        query = query.where(ExportJob.status == status_filter)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(ExportJob.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    jobs = list(result.scalars().all())

    return PaginatedResponse(
        items=[ExportJobResponse.model_validate(j) for j in jobs],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
