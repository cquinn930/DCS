"""Seed jurisdiction-specific policy packs (NJ, NY).

Idempotent. Re-running the script upgrades existing draft packs in place
but never overwrites packs already marked ACTIVE for the same version.

Usage from services/api:
    python scripts/seed_policy_packs.py
    python scripts/seed_policy_packs.py --activate    # activate the latest draft

Legal sources cited inline in each pack. This is non-legal guidance:
verify all rates and citations against the current public source before
relying on the pack for production calculations.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dcs_api.config import get_settings
from dcs_api.models.compliance import (
    DebtCategory,
    PolicyPack,
    PolicyPackStatus,
    RateTable,
    RateTableEntry,
    RateTableType,
    StatuteOfLimitationsRule,
    UsuryRule,
)


# ---------------------------------------------------------------------------
# NEW JERSEY
# ---------------------------------------------------------------------------
#
# Authority for NJ post-judgment interest:
#   N.J. Court Rules, R. 4:42-11(a) (Interest; rate on judgments)
#     - Special Civil Part judgments (claims <= $20,000): rate = average rate
#       of return of the State of New Jersey Cash Management Fund for the
#       prior fiscal year, rounded to nearest one-half percent.
#     - All other judgments: SCP rate + 2 percentage points.
#   The Administrative Office of the Courts publishes the rate annually
#   each January as a Notice to the Bar.
#
# Special Civil Part jurisdictional limit:
#   N.J. Court Rules, R. 6:1-2(a)(1) and N.J.S.A. 2A:6-43 — $20,000.
#
# Statute of limitations:
#   N.J.S.A. 2A:14-1 — 6 years (written contract, open account, oral contract)
#   N.J.S.A. 2A:14-5 — 20 years on a domestic judgment, renewable
#
# Collection agency licensing / bond:
#   N.J.S.A. 45:18-1 et seq. ("Collection Agencies"; administered by
#   NJ Treasury, Division of Revenue and Enterprise Services)
#   N.J.S.A. 45:18-3 — minimum surety bond $5,000
#
# Federal overlays (always apply):
#   FDCPA — 15 U.S.C. § 1692 et seq.
#   Reg F  — 12 C.F.R. Part 1006 (CFPB), incl. § 1006.6 (communications),
#            § 1006.14(b) (7-in-7 call frequency), § 1006.34 (validation
#            information), § 1006.38 (disputes), § 1006.42 (electronic
#            communications consent), § 1006.18 (false/deceptive).
#   TCPA   — 47 U.S.C. § 227 (consent for autodialed calls/texts).

NJ_PACK_VERSION = "nj-2026.1"
NJ_EFFECTIVE_START = date(2026, 1, 1)

NJ_SOURCES: dict[str, dict[str, str]] = {
    "fdcpa": {
        "name": "Fair Debt Collection Practices Act",
        "citation": "15 U.S.C. § 1692 et seq.",
        "url": "https://www.law.cornell.edu/uscode/text/15/chapter-41/subchapter-V",
        "issuer": "U.S. Congress",
    },
    "regulation_f": {
        "name": "CFPB Regulation F — Debt Collection Practices",
        "citation": "12 C.F.R. Part 1006",
        "url": "https://www.consumerfinance.gov/rules-policy/regulations/1006/",
        "issuer": "Consumer Financial Protection Bureau",
    },
    "reg_f_validation": {
        "name": "Reg F validation information requirements",
        "citation": "12 C.F.R. § 1006.34; Model Form B-3 (Appendix B)",
        "url": "https://www.consumerfinance.gov/rules-policy/regulations/1006/34/",
        "issuer": "Consumer Financial Protection Bureau",
    },
    "reg_f_call_frequency": {
        "name": "Reg F 7-in-7 call frequency limit",
        "citation": "12 C.F.R. § 1006.14(b)",
        "url": "https://www.consumerfinance.gov/rules-policy/regulations/1006/14/",
        "issuer": "Consumer Financial Protection Bureau",
    },
    "tcpa": {
        "name": "Telephone Consumer Protection Act",
        "citation": "47 U.S.C. § 227; 47 C.F.R. § 64.1200",
        "url": "https://www.law.cornell.edu/uscode/text/47/227",
        "issuer": "U.S. Congress / FCC",
    },
    "nj_post_judgment_rule": {
        "name": "Interest; Rate on Judgments",
        "citation": "N.J. Court Rules, R. 4:42-11(a)",
        "url": "https://www.njcourts.gov/attorneys/rules-of-court",
        "issuer": "Supreme Court of New Jersey",
    },
    "nj_post_judgment_notice_2026": {
        "name": "AOC Notice to the Bar — 2026 Post-Judgment Interest Rates",
        "citation": "Administrative Office of the Courts (Jan 2026)",
        "url": "https://www.njcourts.gov/notices/notices-bar",
        "issuer": "NJ Administrative Office of the Courts",
    },
    "nj_special_civil_limit": {
        "name": "Special Civil Part jurisdictional limit",
        "citation": "N.J. Court Rules, R. 6:1-2(a)(1); N.J.S.A. 2A:6-43",
        "url": "https://www.njcourts.gov/attorneys/rules-of-court",
        "issuer": "Supreme Court of New Jersey",
    },
    "nj_sol_contracts": {
        "name": "Statute of limitations — contracts and open accounts",
        "citation": "N.J.S.A. 2A:14-1",
        "url": "https://lis.njleg.state.nj.us/nxt/gateway.dll?f=templates&fn=default.htm",
        "issuer": "New Jersey Legislature",
    },
    "nj_sol_judgment": {
        "name": "Statute of limitations — domestic judgment (renewable)",
        "citation": "N.J.S.A. 2A:14-5",
        "url": "https://lis.njleg.state.nj.us/nxt/gateway.dll?f=templates&fn=default.htm",
        "issuer": "New Jersey Legislature",
    },
    "nj_collection_agency_act": {
        "name": "NJ Collection Agencies Act (licensing)",
        "citation": "N.J.S.A. 45:18-1 et seq.",
        "url": "https://lis.njleg.state.nj.us/nxt/gateway.dll?f=templates&fn=default.htm",
        "issuer": "New Jersey Legislature",
    },
    "nj_collection_agency_bond": {
        "name": "NJ Collection Agencies — surety bond minimum",
        "citation": "N.J.S.A. 45:18-3 ($5,000)",
        "url": "https://lis.njleg.state.nj.us/nxt/gateway.dll?f=templates&fn=default.htm",
        "issuer": "New Jersey Legislature",
    },
    "nj_consumer_fraud_act": {
        "name": "NJ Consumer Fraud Act (overlay; treble damages)",
        "citation": "N.J.S.A. 56:8-1 et seq.",
        "url": "https://lis.njleg.state.nj.us/nxt/gateway.dll?f=templates&fn=default.htm",
        "issuer": "New Jersey Legislature",
    },
}

# Source: AOC Notices to the Bar, R. 4:42-11(a). Each year is the post-judgment
# rate for SCP-eligible amounts (<= $20,000 principal). Above-threshold rate is
# always +2.0 percentage points (handled separately at the table level).
NJ_POST_JUDGMENT_RATES: dict[int, str] = {
    2004: "2.0",
    2005: "1.0",
    2006: "2.0",
    2007: "4.0",
    2008: "5.5",
    2009: "4.0",
    2010: "1.5",
    2011: "0.5",
    2012: "0.5",
    2013: "0.25",
    2014: "0.25",
    2015: "0.25",
    2016: "0.25",
    2017: "0.5",
    2018: "0.5",
    2019: "1.5",
    2020: "2.5",
    2021: "1.5",
    2022: "0.25",
    2023: "0.25",
    2024: "3.5",
    2025: "5.5",
    2026: "4.5",
}

NJ_SCP_THRESHOLD_CENTS = 20_000_00  # $20,000 per R. 6:1-2(a)(1)
NJ_BOND_AMOUNT_CENTS = 5_000_00     # $5,000 per N.J.S.A. 45:18-3

# Notice template registry for NJ (template files live under
# dcs_api/notices/templates/nj/).
NJ_NOTICE_TEMPLATES: dict[str, dict[str, str]] = {
    "initial_communication": {
        "template_id": "nj.initial_communication",
        "version": "2026.1",
        "path": "nj/initial_communication.txt",
        "authority": "12 C.F.R. § 1006.34(c)(2)(i)-(ii); 15 U.S.C. § 1692g",
    },
    "validation_notice": {
        "template_id": "nj.validation_notice",
        "version": "2026.1",
        "path": "nj/validation_notice.txt",
        "authority": "12 C.F.R. § 1006.34 + Appendix B Model Form B-3",
    },
    "dispute_acknowledgement": {
        "template_id": "nj.dispute_acknowledgement",
        "version": "2026.1",
        "path": "nj/dispute_acknowledgement.txt",
        "authority": "12 C.F.R. § 1006.38(d); 15 U.S.C. § 1692g(b)",
    },
    "post_judgment_disclosure": {
        "template_id": "nj.post_judgment_disclosure",
        "version": "2026.1",
        "path": "nj/post_judgment_disclosure.txt",
        "authority": "N.J. Court Rules, R. 4:42-11(a)",
    },
}

NJ_SOL_RULES: list[dict] = [
    {
        "category": DebtCategory.WRITTEN_CONTRACT,
        "years": 6,
        "citation": "N.J.S.A. 2A:14-1",
        "notes": "6-year statute applies to written contracts and accounts.",
    },
    {
        "category": DebtCategory.ORAL_CONTRACT,
        "years": 6,
        "citation": "N.J.S.A. 2A:14-1",
        "notes": "NJ uses a single 6-year period for oral and written contracts.",
    },
    {
        "category": DebtCategory.OPEN_ACCOUNT,
        "years": 6,
        "citation": "N.J.S.A. 2A:14-1",
        "notes": "Open-account/credit-card debt — accrual generally on last activity.",
    },
    {
        "category": DebtCategory.PROMISSORY_NOTE,
        "years": 6,
        "citation": "N.J.S.A. 2A:14-1; UCC Art. 3 overlay where applicable",
        "notes": "For non-negotiable notes; negotiable instruments may differ.",
    },
    {
        "category": DebtCategory.JUDGMENT,
        "years": 20,
        "citation": "N.J.S.A. 2A:14-5",
        "notes": "Domestic judgments — renewable for an additional 20 years.",
    },
]

# NJ has no general civil usury cap analogous to NY's 16% rule for most
# commercial credit; consumer rates are constrained by N.J.S.A. 31:1-1
# (general 6%/16% civil/criminal usury) with broad exemptions for licensed
# lenders. We seed the conservative defaults below; tenants should refine
# per debt instrument.
NJ_USURY_RULES: list[dict] = [
    {
        "category": DebtCategory.WRITTEN_CONTRACT,
        "max_rate": "16.0",
        "is_criminal": False,
        "citation": "N.J.S.A. 31:1-1(a)",
        "notes": "16% civil usury cap absent contrary written agreement.",
    },
    {
        "category": DebtCategory.OPEN_ACCOUNT,
        "max_rate": "30.0",
        "is_criminal": False,
        "citation": "N.J.S.A. 31:1-1(b); broad exemptions for licensed lenders",
        "notes": (
            "Open-end consumer credit subject to issuer's contract; "
            "30% used as a defensive flag threshold pending legal review."
        ),
    },
    {
        "category": DebtCategory.JUDGMENT,
        "max_rate": "7.5",
        "is_criminal": False,
        "citation": "R. 4:42-11(a) — rate is set by AOC notice; see rate table",
        "notes": "Judgment 'rate' is statutory; this entry is a guard-rail only.",
    },
]


# ---------------------------------------------------------------------------
# NEW YORK
# ---------------------------------------------------------------------------
#
# Authority for NY post-judgment interest:
#   CPLR § 5004(a) — 9% per annum default rate on judgments.
#   CPLR § 5004(b) (effective Apr. 30, 2022) — 2% per annum on judgments
#     arising out of consumer debt as defined in CPLR § 105(f-1).
#
# Statute of limitations:
#   CPLR § 213(2) — 6 years on contracts.
#   CPLR § 214-i (Consumer Credit Fairness Act, eff. Apr. 7, 2022) —
#     3 years on actions to collect a "consumer credit transaction."
#   CPLR § 211(b) — 20 years on a money judgment.
#
# Collection agency licensing:
#   N.Y. Gen. Bus. Law Art. 29-H §§ 600-603-d (debt collection practices).
#   NYC Admin. Code Title 20, Subchapter 30 (NYC DCWP licensing of
#     collection agencies) — applies to agencies collecting from NYC consumers.
#
# Contact rules: federal floor (Reg F + FDCPA). NY does not narrow further
# at the state level; NYC DCWP rule § 5-77 imposes additional disclosures
# for NYC consumers (handled by an NYC sub-pack in a future revision).

NY_PACK_VERSION = "ny-2026.1"
NY_EFFECTIVE_START = date(2026, 1, 1)

NY_SOURCES: dict[str, dict[str, str]] = {
    "fdcpa": NJ_SOURCES["fdcpa"],
    "regulation_f": NJ_SOURCES["regulation_f"],
    "reg_f_validation": NJ_SOURCES["reg_f_validation"],
    "reg_f_call_frequency": NJ_SOURCES["reg_f_call_frequency"],
    "tcpa": NJ_SOURCES["tcpa"],
    "ny_cplr_5004": {
        "name": "CPLR § 5004 — Rate of interest on judgments",
        "citation": "N.Y. C.P.L.R. § 5004(a)-(b)",
        "url": "https://www.nysenate.gov/legislation/laws/CVP/5004",
        "issuer": "New York State Legislature",
    },
    "ny_consumer_credit_fairness_act": {
        "name": "Consumer Credit Fairness Act — 3-year SOL",
        "citation": "N.Y. C.P.L.R. § 214-i (eff. Apr. 7, 2022)",
        "url": "https://www.nysenate.gov/legislation/laws/CVP/214-I",
        "issuer": "New York State Legislature",
    },
    "ny_cplr_213": {
        "name": "Statute of limitations — contracts (general)",
        "citation": "N.Y. C.P.L.R. § 213(2)",
        "url": "https://www.nysenate.gov/legislation/laws/CVP/213",
        "issuer": "New York State Legislature",
    },
    "ny_cplr_211": {
        "name": "Statute of limitations — money judgment",
        "citation": "N.Y. C.P.L.R. § 211(b)",
        "url": "https://www.nysenate.gov/legislation/laws/CVP/211",
        "issuer": "New York State Legislature",
    },
    "ny_gbl_29h": {
        "name": "NY General Business Law — debt collection practices",
        "citation": "N.Y. Gen. Bus. Law Art. 29-H, §§ 600-603-d",
        "url": "https://www.nysenate.gov/legislation/laws/GBS/A29-H",
        "issuer": "New York State Legislature",
    },
    "nyc_dcwp_licensing": {
        "name": "NYC DCWP debt collection agency licensing",
        "citation": "NYC Admin. Code Title 20, Subch. 30; 6 RCNY § 2-191 et seq.",
        "url": "https://www.nyc.gov/site/dca/businesses/license-checklist-debt-collection-agency.page",
        "issuer": "NYC Department of Consumer and Worker Protection",
    },
}

NY_POST_JUDGMENT_RATE_DEFAULT = "9.0"   # CPLR § 5004(a)
NY_POST_JUDGMENT_RATE_CONSUMER = "2.0"  # CPLR § 5004(b) — eff. Apr. 30, 2022

NY_NOTICE_TEMPLATES: dict[str, dict[str, str]] = {
    "initial_communication": {
        "template_id": "ny.initial_communication",
        "version": "2026.1",
        "path": "ny/initial_communication.txt",
        "authority": "12 C.F.R. § 1006.34(c)(2); 15 U.S.C. § 1692g; CPLR § 214-i overlay",
    },
    "validation_notice": {
        "template_id": "ny.validation_notice",
        "version": "2026.1",
        "path": "ny/validation_notice.txt",
        "authority": "12 C.F.R. § 1006.34 + Appendix B Model Form B-3",
    },
    "dispute_acknowledgement": {
        "template_id": "ny.dispute_acknowledgement",
        "version": "2026.1",
        "path": "ny/dispute_acknowledgement.txt",
        "authority": "12 C.F.R. § 1006.38(d); 15 U.S.C. § 1692g(b)",
    },
    "post_judgment_disclosure": {
        "template_id": "ny.post_judgment_disclosure",
        "version": "2026.1",
        "path": "ny/post_judgment_disclosure.txt",
        "authority": "N.Y. C.P.L.R. § 5004(a)-(b)",
    },
}

NY_SOL_RULES: list[dict] = [
    {
        "category": DebtCategory.WRITTEN_CONTRACT,
        "years": 6,
        "citation": "N.Y. C.P.L.R. § 213(2)",
        "notes": "Default 6-year SOL for non-consumer contract claims.",
    },
    {
        "category": DebtCategory.OPEN_ACCOUNT,
        "years": 3,
        "citation": "N.Y. C.P.L.R. § 214-i (Consumer Credit Fairness Act)",
        "notes": (
            "Consumer-credit transactions reduced from 6 to 3 years effective "
            "Apr. 7, 2022. Non-consumer open accounts remain at 6 years."
        ),
    },
    {
        "category": DebtCategory.PROMISSORY_NOTE,
        "years": 6,
        "citation": "N.Y. C.P.L.R. § 213(2); UCC Art. 3 overlay",
        "notes": "Negotiable-instrument analysis may shorten or extend.",
    },
    {
        "category": DebtCategory.JUDGMENT,
        "years": 20,
        "citation": "N.Y. C.P.L.R. § 211(b)",
        "notes": "Money judgments — renewable.",
    },
]

NY_USURY_RULES: list[dict] = [
    {
        "category": DebtCategory.WRITTEN_CONTRACT,
        "max_rate": "16.0",
        "is_criminal": False,
        "citation": "N.Y. Gen. Oblig. Law § 5-501; N.Y. Banking Law § 14-a",
        "notes": "Civil usury cap; many exemptions for licensed lenders.",
    },
    {
        "category": DebtCategory.WRITTEN_CONTRACT,
        "max_rate": "25.0",
        "is_criminal": True,
        "citation": "N.Y. Penal Law § 190.40",
        "notes": "Criminal usury — second-degree.",
    },
    {
        "category": DebtCategory.JUDGMENT,
        "max_rate": "9.0",
        "is_criminal": False,
        "citation": "CPLR § 5004(a) (consumer judgments capped at 2% by § 5004(b))",
        "notes": "Statutory rate; this is a guard-rail entry.",
    },
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------


async def _upsert_pack(
    session: AsyncSession,
    *,
    jurisdiction: str,
    version: str,
    name: str,
    description: str,
    effective_start: date,
    sources: dict,
    notice_templates: dict,
    bond_amount_cents: int | None,
) -> PolicyPack:
    """Insert or update a draft pack. Refuses to overwrite ACTIVE packs."""
    existing = await session.execute(
        select(PolicyPack).where(
            PolicyPack.jurisdiction == jurisdiction,
            PolicyPack.version == version,
        )
    )
    pack = existing.scalar_one_or_none()
    if pack and pack.status == PolicyPackStatus.ACTIVE:
        print(
            f"  [skip] {jurisdiction} {version} is ACTIVE — refusing to mutate. "
            "Bump the version to seed an update."
        )
        return pack
    if pack is None:
        pack = PolicyPack(
            id=uuid.uuid4(),
            jurisdiction=jurisdiction,
            version=version,
            name=name,
            description=description,
            status=PolicyPackStatus.DRAFT,
            effective_start=effective_start,
            sources=sources,
            notice_templates=notice_templates,
            default_bond_amount=bond_amount_cents,
        )
        session.add(pack)
    else:
        pack.name = name
        pack.description = description
        pack.sources = sources
        pack.notice_templates = notice_templates
        pack.default_bond_amount = bond_amount_cents
        pack.effective_start = effective_start
    await session.flush()
    return pack


async def _replace_rate_table(
    session: AsyncSession,
    *,
    pack: PolicyPack,
    rate_type: RateTableType,
    name: str,
    description: str,
    source_name: str,
    source_url: str | None,
    threshold_amount: int | None,
    above_threshold_adjustment: Decimal | None,
    entries: dict[int, str] | None,
) -> RateTable:
    """Replace any existing rate table of the given type for the pack."""
    existing = await session.execute(
        select(RateTable).where(
            RateTable.policy_pack_id == pack.id,
            RateTable.rate_type == rate_type,
        )
    )
    for old in existing.scalars():
        await session.delete(old)
    await session.flush()

    table = RateTable(
        id=uuid.uuid4(),
        policy_pack_id=pack.id,
        name=name,
        rate_type=rate_type,
        description=description,
        source_name=source_name,
        source_url=source_url,
        threshold_amount=threshold_amount,
        above_threshold_adjustment=above_threshold_adjustment,
    )
    session.add(table)
    await session.flush()

    if entries:
        for year, rate in entries.items():
            session.add(
                RateTableEntry(
                    id=uuid.uuid4(),
                    rate_table_id=table.id,
                    effective_year=year,
                    effective_date=date(year, 1, 1),
                    rate=Decimal(rate),
                )
            )
    await session.flush()
    return table


async def _replace_sol_rules(
    session: AsyncSession, pack: PolicyPack, rules: list[dict]
) -> None:
    existing = await session.execute(
        select(StatuteOfLimitationsRule).where(
            StatuteOfLimitationsRule.policy_pack_id == pack.id
        )
    )
    for old in existing.scalars():
        await session.delete(old)
    await session.flush()

    for rule in rules:
        session.add(
            StatuteOfLimitationsRule(
                id=uuid.uuid4(),
                policy_pack_id=pack.id,
                debt_category=rule["category"],
                limitation_years=rule["years"],
                statute_citation=rule["citation"],
                notes=rule.get("notes"),
            )
        )
    await session.flush()


async def _replace_usury_rules(
    session: AsyncSession, pack: PolicyPack, rules: list[dict]
) -> None:
    existing = await session.execute(
        select(UsuryRule).where(UsuryRule.policy_pack_id == pack.id)
    )
    for old in existing.scalars():
        await session.delete(old)
    await session.flush()

    for rule in rules:
        session.add(
            UsuryRule(
                id=uuid.uuid4(),
                policy_pack_id=pack.id,
                debt_category=rule["category"],
                max_rate=Decimal(rule["max_rate"]),
                is_criminal=rule.get("is_criminal", False),
                statute_citation=rule.get("citation"),
                exemptions=rule.get("exemptions", {}),
                notes=rule.get("notes"),
            )
        )
    await session.flush()


async def seed_nj_pack(session: AsyncSession) -> PolicyPack:
    print(f"[NJ] seeding pack {NJ_PACK_VERSION}...")
    pack = await _upsert_pack(
        session,
        jurisdiction="NJ",
        version=NJ_PACK_VERSION,
        name="New Jersey 2026 policy pack",
        description=(
            "Federal FDCPA + Reg F overlay with NJ post-judgment interest "
            "(R. 4:42-11(a)), NJ statutes of limitations (Title 2A:14), and "
            "NJ collection-agency licensing (N.J.S.A. 45:18 et seq.)."
        ),
        effective_start=NJ_EFFECTIVE_START,
        sources=NJ_SOURCES,
        notice_templates=NJ_NOTICE_TEMPLATES,
        bond_amount_cents=NJ_BOND_AMOUNT_CENTS,
    )

    pack.contact_window_start = "08:00"
    pack.contact_window_end = "21:00"
    # Reg F § 1006.14(b) 7-in-7 rule. Daily floor of 1 contact attempt and a
    # weekly cap of 7 (across all phone calls to the same consumer for the
    # same debt). Tenants may tighten further.
    pack.max_daily_contacts = 1
    pack.max_weekly_contacts = 7
    pack.validation_notice_days = 5     # 15 U.S.C. § 1692g(a)
    pack.dispute_response_days = 30     # § 1006.38; § 1692g(b)
    pack.license_required = True
    pack.bond_required = True

    await _replace_rate_table(
        session,
        pack=pack,
        rate_type=RateTableType.POST_JUDGMENT_STANDARD,
        name="NJ post-judgment interest (Special Civil Part)",
        description=(
            "Annual rate published by the AOC under R. 4:42-11(a) for "
            "judgments at or below the $20,000 SCP threshold. "
            "Above-threshold judgments use rate + 2.0%."
        ),
        source_name="NJ Courts Rule 4:42-11(a) — AOC annual notice",
        source_url=NJ_SOURCES["nj_post_judgment_rule"]["url"],
        threshold_amount=NJ_SCP_THRESHOLD_CENTS,
        above_threshold_adjustment=Decimal("2.0"),
        entries=NJ_POST_JUDGMENT_RATES,
    )

    await _replace_sol_rules(session, pack, NJ_SOL_RULES)
    await _replace_usury_rules(session, pack, NJ_USURY_RULES)
    print(f"[NJ] pack {pack.version} ({pack.id}) seeded")
    return pack


async def seed_ny_pack(session: AsyncSession) -> PolicyPack:
    print(f"[NY] seeding pack {NY_PACK_VERSION}...")
    pack = await _upsert_pack(
        session,
        jurisdiction="NY",
        version=NY_PACK_VERSION,
        name="New York 2026 policy pack",
        description=(
            "Federal FDCPA + Reg F overlay with NY post-judgment interest "
            "(CPLR § 5004), Consumer Credit Fairness Act 3-year SOL "
            "(CPLR § 214-i), and NY GBL Art. 29-H collection rules."
        ),
        effective_start=NY_EFFECTIVE_START,
        sources=NY_SOURCES,
        notice_templates=NY_NOTICE_TEMPLATES,
        bond_amount_cents=None,  # NY state has no flat statewide bond; NYC differs
    )

    pack.contact_window_start = "08:00"
    pack.contact_window_end = "21:00"
    pack.max_daily_contacts = 1
    pack.max_weekly_contacts = 7
    pack.validation_notice_days = 5
    pack.dispute_response_days = 30
    pack.license_required = True   # NYC DCWP and many counties require licensing
    pack.bond_required = False     # state-level — NYC sub-pack would override

    # Default (non-consumer) judgment rate
    await _replace_rate_table(
        session,
        pack=pack,
        rate_type=RateTableType.POST_JUDGMENT_STANDARD,
        name="NY post-judgment interest (default 9% per CPLR § 5004(a))",
        description=(
            "9% per annum default judgment rate. Applies to judgments not "
            "arising out of a consumer credit transaction."
        ),
        source_name="N.Y. C.P.L.R. § 5004(a)",
        source_url=NY_SOURCES["ny_cplr_5004"]["url"],
        threshold_amount=None,
        above_threshold_adjustment=None,
        entries={year: NY_POST_JUDGMENT_RATE_DEFAULT for year in range(2004, 2027)},
    )

    # Consumer-debt judgment rate (CPLR § 5004(b) eff. Apr. 30, 2022)
    await _replace_rate_table(
        session,
        pack=pack,
        rate_type=RateTableType.POST_JUDGMENT_ABOVE_THRESHOLD,
        name="NY consumer-debt post-judgment interest (CPLR § 5004(b))",
        description=(
            "2% per annum on judgments arising out of consumer debt. "
            "Effective Apr. 30, 2022."
        ),
        source_name="N.Y. C.P.L.R. § 5004(b)",
        source_url=NY_SOURCES["ny_cplr_5004"]["url"],
        threshold_amount=None,
        above_threshold_adjustment=None,
        entries={year: NY_POST_JUDGMENT_RATE_CONSUMER for year in range(2022, 2027)},
    )

    await _replace_sol_rules(session, pack, NY_SOL_RULES)
    await _replace_usury_rules(session, pack, NY_USURY_RULES)
    print(f"[NY] pack {pack.version} ({pack.id}) seeded")
    return pack


async def main(activate: bool = False) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            nj = await seed_nj_pack(session)
            ny = await seed_ny_pack(session)

            if activate:
                # Demote any prior ACTIVE packs for the same jurisdiction to
                # SUPERSEDED before activating the new one.
                for pack in (nj, ny):
                    prior = await session.execute(
                        select(PolicyPack).where(
                            PolicyPack.jurisdiction == pack.jurisdiction,
                            PolicyPack.status == PolicyPackStatus.ACTIVE,
                            PolicyPack.id != pack.id,
                        )
                    )
                    for old in prior.scalars():
                        old.status = PolicyPackStatus.SUPERSEDED
                        old.effective_end = pack.effective_start
                    pack.status = PolicyPackStatus.ACTIVE
                await session.flush()
                print("Activated NJ and NY packs.")

            await session.commit()

            print("\n=== Policy pack seed complete ===")
            print(f"  NJ: {nj.version} status={nj.status.value} id={nj.id}")
            print(f"  NY: {ny.version} status={ny.status.value} id={ny.id}")
            print(
                "Disclaimer: Non-legal guidance. Rates, statute citations, "
                "and source URLs were captured from public materials and must "
                "be reviewed by qualified counsel before relying on them in "
                "production calculations or notices."
            )
    except Exception as exc:
        print("Policy-pack seed failed:", exc, file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1) from exc
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Mark the seeded packs ACTIVE (and supersede any prior ACTIVE pack)",
    )
    args = parser.parse_args()
    asyncio.run(main(activate=args.activate))
