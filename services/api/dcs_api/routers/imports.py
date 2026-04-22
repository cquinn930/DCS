"""Import engine endpoints.

Tenants define import templates per client / creditor / jurisdiction
with field mappings, transformations, and validation rules, then
upload files to be processed.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.engines.importing import parse_csv, parse_fixed_width, process_import
from dcs_api.models.customization import (
    DedupStrategy,
    ImportEntity,
    ImportFormat,
    ImportJob,
    ImportTemplate,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.customization import (
    ImportJobResponse,
    ImportTemplateCreate,
    ImportTemplateResponse,
    ImportTemplateUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("/templates", response_model=PaginatedResponse[ImportTemplateResponse])
async def list_import_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    entity: str | None = None,
    client_name: str | None = None,
    jurisdiction: str | None = None,
) -> PaginatedResponse[ImportTemplateResponse]:
    query = select(ImportTemplate).where(ImportTemplate.tenant_id == user.tenant_id)

    if entity:
        query = query.where(ImportTemplate.entity == entity)
    if client_name:
        query = query.where(ImportTemplate.client_name == client_name)
    if jurisdiction:
        query = query.where(ImportTemplate.jurisdiction == jurisdiction.upper())

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(ImportTemplate.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    templates = list(result.scalars().all())

    return PaginatedResponse(
        items=[ImportTemplateResponse.model_validate(t) for t in templates],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/templates/{template_id}", response_model=ImportTemplateResponse)
async def get_import_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ImportTemplateResponse:
    query = select(ImportTemplate).where(
        ImportTemplate.id == template_id, ImportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import template not found")
    return ImportTemplateResponse.model_validate(template)


@router.post("/templates", response_model=ImportTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_import_template(
    data: ImportTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> ImportTemplateResponse:
    template = ImportTemplate(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        source_format=ImportFormat(data.source_format),
        entity=ImportEntity(data.entity),
        field_mappings=[fm.model_dump() for fm in data.field_mappings],
        validation_rules=[vr.model_dump() for vr in data.validation_rules],
        transformations=data.transformations,
        default_values=data.default_values,
        delimiter=data.delimiter,
        encoding=data.encoding,
        skip_header_rows=data.skip_header_rows,
        fixed_width_spec=data.fixed_width_spec,
        dedup_strategy=DedupStrategy(data.dedup_strategy),
        dedup_fields=data.dedup_fields,
        client_name=data.client_name,
        jurisdiction=data.jurisdiction.upper() if data.jurisdiction else None,
        created_by=user.user_id,
    )
    session.add(template)
    await session.flush()
    return ImportTemplateResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=ImportTemplateResponse)
async def update_import_template(
    template_id: uuid.UUID,
    data: ImportTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> ImportTemplateResponse:
    query = select(ImportTemplate).where(
        ImportTemplate.id == template_id, ImportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import template not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "field_mappings" and isinstance(value, list):
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        if key == "validation_rules" and isinstance(value, list):
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(template, key, value)

    await session.flush()
    return ImportTemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import_template(
    template_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
) -> None:
    query = select(ImportTemplate).where(
        ImportTemplate.id == template_id, ImportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import template not found")
    await session.delete(template)


@router.post("/templates/{template_id}/run")
async def run_import(
    template_id: uuid.UUID,
    file_content: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_ACCOUNT_CONTACT))],
    file_name: str = "upload.csv",
) -> ImportJobResponse:
    """Run an import using a saved template.

    In production this would accept multipart file upload.
    For the API, pass raw file content as the request body string.
    """
    query = select(ImportTemplate).where(
        ImportTemplate.id == template_id, ImportTemplate.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import template not found")

    now = datetime.now(timezone.utc)
    job = ImportJob(
        tenant_id=user.tenant_id,
        template_id=template.id,
        file_name=file_name,
        file_size=len(file_content.encode()),
        status="running",
        started_at=now,
        created_by=user.user_id,
    )
    session.add(job)
    await session.flush()

    try:
        if template.source_format == ImportFormat.CSV:
            rows = parse_csv(file_content, template.delimiter, template.skip_header_rows)
        elif template.source_format == ImportFormat.FIXED_WIDTH and template.fixed_width_spec:
            rows = parse_fixed_width(file_content, template.fixed_width_spec, template.skip_header_rows)
        elif template.source_format == ImportFormat.JSON:
            import json
            rows = json.loads(file_content)
            if not isinstance(rows, list):
                rows = [rows]
        else:
            raise ValueError(f"Unsupported format: {template.source_format}")

        import_result = await process_import(
            session=session,
            tenant_id=user.tenant_id,
            source_rows=rows,
            field_mappings=template.field_mappings,
            validation_rules=template.validation_rules,
            default_values=template.default_values,
            entity=template.entity.value,
            dedup_strategy=template.dedup_strategy.value,
            dedup_fields=template.dedup_fields,
            user_id=user.user_id,
        )

        job.status = "completed"
        job.total_rows = import_result["total_rows"]
        job.processed_rows = import_result["processed_rows"]
        job.created_rows = import_result["created_rows"]
        job.updated_rows = import_result["updated_rows"]
        job.skipped_rows = import_result["skipped_rows"]
        job.error_rows = import_result["error_rows"]
        job.errors = import_result["errors"]
        job.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        job.status = "failed"
        job.errors = [{"error": str(e)}]
        job.completed_at = datetime.now(timezone.utc)

    await session.flush()
    return ImportJobResponse.model_validate(job)


@router.get("/jobs", response_model=PaginatedResponse[ImportJobResponse])
async def list_import_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: str | None = None,
) -> PaginatedResponse[ImportJobResponse]:
    query = select(ImportJob).where(ImportJob.tenant_id == user.tenant_id)
    if status_filter:
        query = query.where(ImportJob.status == status_filter)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.order_by(ImportJob.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    jobs = list(result.scalars().all())

    return PaginatedResponse(
        items=[ImportJobResponse.model_validate(j) for j in jobs],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
) -> ImportJobResponse:
    query = select(ImportJob).where(
        ImportJob.id == job_id, ImportJob.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    return ImportJobResponse.model_validate(job)
