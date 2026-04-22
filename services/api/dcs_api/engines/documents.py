"""Document merge engine.

Resolves merge fields in document templates using account, consumer,
and related entity data to produce rendered document content.
"""

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.models.account import Account
from dcs_api.models.consumer import Consumer
from dcs_api.models.documents import (
    DocumentGeneration,
    DocumentTemplate,
    GenerationStatus,
)


async def resolve_merge_fields(
    session: AsyncSession,
    account_id,
    tenant_id,
) -> dict:
    """Build the merge field dictionary for an account."""
    query = (
        select(Account)
        .where(Account.id == account_id, Account.tenant_id == tenant_id)
        .options(selectinload(Account.consumer))
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        return {}

    consumer = account.consumer
    now = datetime.now(timezone.utc)

    fields = {
        "account.id": str(account.id),
        "account.reference": account.account_reference,
        "account.original_creditor": account.original_creditor,
        "account.current_creditor": account.current_creditor or account.original_creditor,
        "account.status": account.status.value if account.status else "",
        "account.debt_type": account.debt_type.value if account.debt_type else "",
        "account.jurisdiction": account.jurisdiction,
        "account.original_principal": _cents_to_dollars(account.original_principal),
        "account.current_principal": _cents_to_dollars(account.current_principal),
        "account.current_interest": _cents_to_dollars(account.current_interest),
        "account.current_fees": _cents_to_dollars(account.current_fees),
        "account.total_balance": _cents_to_dollars(account.total_balance),
        "account.date_placed": _format_date(account.date_placed),
        "account.date_of_service": _format_date(account.date_of_service),
        "account.client_account_number": account.client_account_number or "",
    }

    if consumer:
        fields.update({
            "consumer.id": str(consumer.id),
            "consumer.first_name": consumer.first_name or "",
            "consumer.last_name": consumer.last_name or "",
            "consumer.full_name": f"{consumer.first_name or ''} {consumer.last_name or ''}".strip(),
            "consumer.external_id": consumer.external_id or "",
        })

    fields.update({
        "date.today": now.strftime("%m/%d/%Y"),
        "date.today_long": now.strftime("%B %d, %Y"),
        "date.year": str(now.year),
    })

    return fields


async def generate_document(
    session: AsyncSession,
    template: DocumentTemplate,
    account_id,
    tenant_id,
    *,
    channel: str = "print",
    generated_by_id=None,
    extra_fields: dict | None = None,
) -> DocumentGeneration:
    """Render a document template for a specific account."""
    merge_data = await resolve_merge_fields(session, account_id, tenant_id)

    if extra_fields:
        merge_data.update(extra_fields)

    rendered_body = _apply_merge(template.body, merge_data)
    rendered_subject = _apply_merge(template.subject, merge_data) if template.subject else None

    if template.header:
        rendered_body = _apply_merge(template.header, merge_data) + "\n" + rendered_body
    if template.footer:
        rendered_body = rendered_body + "\n" + _apply_merge(template.footer, merge_data)

    content_hash = hashlib.sha256(rendered_body.encode()).hexdigest()

    gen = DocumentGeneration(
        tenant_id=tenant_id,
        template_id=template.id,
        account_id=account_id,
        status=GenerationStatus.COMPLETED,
        channel=channel,
        rendered_subject=rendered_subject,
        rendered_body=rendered_body,
        content_hash=content_hash,
        merge_data=merge_data,
        generated_at=datetime.now(timezone.utc),
        generated_by_id=generated_by_id,
    )
    session.add(gen)
    return gen


def _apply_merge(template_text: str, fields: dict) -> str:
    """Replace {{field.name}} placeholders with values."""
    def replacer(match):
        key = match.group(1).strip()
        return str(fields.get(key, f"[{key}]"))

    return re.sub(r"\{\{(.+?)\}\}", replacer, template_text)


def _cents_to_dollars(cents: int | None) -> str:
    if cents is None:
        return "$0.00"
    return f"${cents / 100:,.2f}"


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%m/%d/%Y")
