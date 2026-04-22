"""Compliance and policy pack endpoints.

cursor.stage: compliance
cursor.jurisdiction: NJ
cursor.sources: []

Non-legal guidance: Compliance features assist with regulatory adherence
but do not guarantee compliance. Consult legal counsel.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.compliance import (
    DebtCategory,
    PolicyPack,
    PolicyPackStatus,
    RateTable,
    RateTableEntry,
    StatuteOfLimitationsRule,
    UsuryRule,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/policy-packs")
async def list_policy_packs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    jurisdiction: str | None = None,
    status_filter: PolicyPackStatus | None = None,
) -> list[dict]:
    """List available policy packs."""
    query = select(PolicyPack)

    if jurisdiction:
        query = query.where(PolicyPack.jurisdiction == jurisdiction.upper())
    if status_filter:
        query = query.where(PolicyPack.status == status_filter)

    result = await session.execute(query)
    packs = list(result.scalars().all())

    return [p.to_dict() for p in packs]


@router.get("/policy-packs/{pack_id}")
async def get_policy_pack(
    pack_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Get policy pack details."""
    query = (
        select(PolicyPack)
        .where(PolicyPack.id == pack_id)
        .options(
            selectinload(PolicyPack.rate_tables).selectinload(RateTable.entries),
            selectinload(PolicyPack.sol_rules),
            selectinload(PolicyPack.usury_rules),
        )
    )
    result = await session.execute(query)
    pack = result.scalar_one_or_none()

    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy pack not found",
        )

    return {
        **pack.to_dict(),
        "rate_tables": [
            {
                **rt.to_dict(),
                "entries": [e.to_dict() for e in rt.entries],
            }
            for rt in pack.rate_tables
        ],
        "statute_of_limitations": [r.to_dict() for r in pack.sol_rules],
        "usury_rules": [r.to_dict() for r in pack.usury_rules],
    }


@router.get("/policy-packs/active/{jurisdiction}")
async def get_active_policy_pack(
    jurisdiction: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Get the currently active policy pack for a jurisdiction."""
    query = (
        select(PolicyPack)
        .where(
            PolicyPack.jurisdiction == jurisdiction.upper(),
            PolicyPack.status == PolicyPackStatus.ACTIVE,
        )
        .options(
            selectinload(PolicyPack.rate_tables).selectinload(RateTable.entries),
            selectinload(PolicyPack.sol_rules),
            selectinload(PolicyPack.usury_rules),
        )
    )
    result = await session.execute(query)
    pack = result.scalar_one_or_none()

    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active policy pack for jurisdiction {jurisdiction}",
        )

    return pack.to_dict()


@router.get("/statute-of-limitations/{jurisdiction}/{debt_category}")
async def get_statute_of_limitations(
    jurisdiction: str,
    debt_category: DebtCategory,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Get statute of limitations for a debt category.

    cursor.stage: compliance
    cursor.jurisdiction: NJ
    cursor.sources: []

    Non-legal guidance: Statute of limitations varies by jurisdiction and
    debt type. Verify against current law.
    """
    # Get active policy pack for jurisdiction
    pack_query = select(PolicyPack).where(
        PolicyPack.jurisdiction == jurisdiction.upper(),
        PolicyPack.status == PolicyPackStatus.ACTIVE,
    )
    pack_result = await session.execute(pack_query)
    pack = pack_result.scalar_one_or_none()

    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active policy pack for jurisdiction {jurisdiction}",
        )

    # Get SOL rule
    sol_query = select(StatuteOfLimitationsRule).where(
        StatuteOfLimitationsRule.policy_pack_id == pack.id,
        StatuteOfLimitationsRule.debt_category == debt_category,
    )
    sol_result = await session.execute(sol_query)
    sol = sol_result.scalar_one_or_none()

    if not sol:
        return {
            "jurisdiction": jurisdiction.upper(),
            "debt_category": debt_category.value,
            "limitation_years": None,
            "statute_citation": None,
            "disclaimer": "Non-legal guidance: SOL rule not found. Verify with legal counsel.",
        }

    return {
        "jurisdiction": jurisdiction.upper(),
        "debt_category": debt_category.value,
        "limitation_years": sol.limitation_years,
        "statute_citation": sol.statute_citation,
        "notes": sol.notes,
        "policy_pack_version": pack.version,
        "disclaimer": "Non-legal guidance: Verify SOL against current law.",
    }


@router.get("/usury-limit/{jurisdiction}/{debt_category}")
async def get_usury_limit(
    jurisdiction: str,
    debt_category: DebtCategory,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Get usury limit for a debt category.

    cursor.stage: compliance
    cursor.jurisdiction: NJ
    cursor.sources: []

    Non-legal guidance: Interest rates exceeding usury limits may be unenforceable
    or subject to criminal penalties.
    """
    # Get active policy pack
    pack_query = select(PolicyPack).where(
        PolicyPack.jurisdiction == jurisdiction.upper(),
        PolicyPack.status == PolicyPackStatus.ACTIVE,
    )
    pack_result = await session.execute(pack_query)
    pack = pack_result.scalar_one_or_none()

    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active policy pack for jurisdiction {jurisdiction}",
        )

    # Get usury rule
    usury_query = select(UsuryRule).where(
        UsuryRule.policy_pack_id == pack.id,
        UsuryRule.debt_category == debt_category,
    )
    usury_result = await session.execute(usury_query)
    usury = usury_result.scalar_one_or_none()

    if not usury:
        return {
            "jurisdiction": jurisdiction.upper(),
            "debt_category": debt_category.value,
            "max_rate": None,
            "disclaimer": "Non-legal guidance: Usury rule not found. Verify with legal counsel.",
        }

    return {
        "jurisdiction": jurisdiction.upper(),
        "debt_category": debt_category.value,
        "max_rate": float(usury.max_rate),
        "is_criminal": usury.is_criminal,
        "statute_citation": usury.statute_citation,
        "exemptions": usury.exemptions,
        "notes": usury.notes,
        "disclaimer": "Non-legal guidance: Verify usury limits against current law.",
    }


@router.get("/contact-rules/{jurisdiction}")
async def get_contact_rules(
    jurisdiction: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Get contact rules for a jurisdiction.

    cursor.stage: compliance
    cursor.jurisdiction: NJ
    cursor.sources: ["FDCPA", "CFPB Regulation F"]

    Non-legal guidance: Contact rules include time windows and frequency limits.
    """
    pack_query = select(PolicyPack).where(
        PolicyPack.jurisdiction == jurisdiction.upper(),
        PolicyPack.status == PolicyPackStatus.ACTIVE,
    )
    pack_result = await session.execute(pack_query)
    pack = pack_result.scalar_one_or_none()

    if not pack:
        # Return FDCPA defaults
        return {
            "jurisdiction": jurisdiction.upper(),
            "contact_window_start": "08:00",
            "contact_window_end": "21:00",
            "max_daily_contacts": 1,
            "max_weekly_contacts": 7,
            "source": "FDCPA / Regulation F defaults",
            "disclaimer": "Non-legal guidance: Verify contact rules against current regulations.",
        }

    return {
        "jurisdiction": jurisdiction.upper(),
        "contact_window_start": pack.contact_window_start,
        "contact_window_end": pack.contact_window_end,
        "max_daily_contacts": pack.max_daily_contacts,
        "max_weekly_contacts": pack.max_weekly_contacts,
        "validation_notice_days": pack.validation_notice_days,
        "dispute_response_days": pack.dispute_response_days,
        "policy_pack_version": pack.version,
        "disclaimer": "Non-legal guidance: Verify contact rules against current regulations.",
    }


@router.post("/validate-rate")
async def validate_interest_rate(
    jurisdiction: str,
    debt_category: DebtCategory,
    rate: float,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Validate an interest rate against usury limits.

    Non-legal guidance: Rates exceeding limits should be flagged for legal review.
    """
    usury_result = await get_usury_limit(jurisdiction, debt_category, session, user)

    if usury_result.get("max_rate") is None:
        return {
            "rate": rate,
            "is_valid": None,
            "message": "Unable to validate - no usury rule found",
            "requires_review": True,
        }

    max_rate = usury_result["max_rate"]
    is_valid = rate <= max_rate

    return {
        "rate": rate,
        "max_rate": max_rate,
        "is_valid": is_valid,
        "requires_review": not is_valid,
        "message": (
            "Rate within limits"
            if is_valid
            else f"Rate exceeds usury limit of {max_rate}% - requires legal review"
        ),
        "is_criminal": usury_result.get("is_criminal", False) if not is_valid else False,
    }
