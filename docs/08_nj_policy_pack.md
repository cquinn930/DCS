## NJ policy pack (v2026.1)

This is the New Jersey policy pack. It is versioned and attached to every
calculation, notice, and compliance decision. The canonical store is the
`policy_packs` / `rate_tables` / `statute_of_limitations_rules` /
`usury_rules` tables; the seeded values come from
`services/api/scripts/seed_policy_packs.py`.

> **Non-legal guidance.** All citations and rates below were captured
> from public materials and must be re-verified by qualified New Jersey
> counsel before relying on the pack for production calculations or
> consumer-facing notices.

### Policy pack metadata

| Field            | Value                                       |
|------------------|---------------------------------------------|
| Jurisdiction     | NJ                                          |
| Pack version     | `nj-2026.1`                                 |
| Effective start  | 2026-01-01                                  |
| Effective end    | open                                        |
| Status           | DRAFT (set ACTIVE via `--activate` flag)    |
| Source verification | Captured 2026; re-verify each January   |

### Source registry

Each entry below is also persisted in `policy_packs.sources` as JSONB so
audit logs can resolve the citation that controlled a given decision.

| Key                         | Authority                                       | Citation                                                          |
|-----------------------------|-------------------------------------------------|-------------------------------------------------------------------|
| `fdcpa`                     | U.S. Congress                                   | 15 U.S.C. § 1692 et seq.                                          |
| `regulation_f`              | CFPB                                            | 12 C.F.R. Part 1006                                               |
| `reg_f_validation`          | CFPB (validation information)                   | 12 C.F.R. § 1006.34; Appendix B Model Form B-3                    |
| `reg_f_call_frequency`      | CFPB (7-in-7 rule)                              | 12 C.F.R. § 1006.14(b)                                            |
| `tcpa`                      | U.S. Congress / FCC                             | 47 U.S.C. § 227; 47 C.F.R. § 64.1200                              |
| `nj_post_judgment_rule`     | Supreme Court of New Jersey                     | N.J. Court Rules, R. 4:42-11(a)                                   |
| `nj_post_judgment_notice_2026` | NJ Administrative Office of the Courts       | AOC Notice to the Bar (annual; January each year)                 |
| `nj_special_civil_limit`    | Supreme Court of New Jersey                     | R. 6:1-2(a)(1); N.J.S.A. 2A:6-43 — $20,000                        |
| `nj_sol_contracts`          | New Jersey Legislature                          | N.J.S.A. 2A:14-1 (6 years)                                        |
| `nj_sol_judgment`           | New Jersey Legislature                          | N.J.S.A. 2A:14-5 (20 years, renewable)                            |
| `nj_collection_agency_act`  | New Jersey Legislature                          | N.J.S.A. 45:18-1 et seq.                                          |
| `nj_collection_agency_bond` | New Jersey Legislature                          | N.J.S.A. 45:18-3 ($5,000 bond minimum)                            |
| `nj_consumer_fraud_act`     | New Jersey Legislature                          | N.J.S.A. 56:8-1 et seq. (overlay; treble damages)                 |

URLs are stored in the JSON registry; key references:

* NJ Court Rules: `https://www.njcourts.gov/attorneys/rules-of-court`
* AOC Notices to the Bar: `https://www.njcourts.gov/notices/notices-bar`
* NJ Statutes (LIS): `https://lis.njleg.state.nj.us/`
* CFPB Reg F: `https://www.consumerfinance.gov/rules-policy/regulations/1006/`

### Post-judgment interest rate table

Authority: **N.J. Court Rules, R. 4:42-11(a)**.

* Below the $20,000 Special Civil Part threshold (R. 6:1-2(a)(1)): rate
  equals the average rate of return of the State of New Jersey Cash
  Management Fund for the prior fiscal year, rounded to the nearest
  half-percent. Published each January by the AOC.
* Above the threshold: SCP rate **+ 2.0** percentage points.

| Year | SCP rate | Above-threshold (SCP + 2%) |
|------|---------:|---------------------------:|
| 2004 | 2.00%    | 4.00%                      |
| 2005 | 1.00%    | 3.00%                      |
| 2006 | 2.00%    | 4.00%                      |
| 2007 | 4.00%    | 6.00%                      |
| 2008 | 5.50%    | 7.50%                      |
| 2009 | 4.00%    | 6.00%                      |
| 2010 | 1.50%    | 3.50%                      |
| 2011 | 0.50%    | 2.50%                      |
| 2012 | 0.50%    | 2.50%                      |
| 2013 | 0.25%    | 2.25%                      |
| 2014 | 0.25%    | 2.25%                      |
| 2015 | 0.25%    | 2.25%                      |
| 2016 | 0.25%    | 2.25%                      |
| 2017 | 0.50%    | 2.50%                      |
| 2018 | 0.50%    | 2.50%                      |
| 2019 | 1.50%    | 3.50%                      |
| 2020 | 2.50%    | 4.50%                      |
| 2021 | 1.50%    | 3.50%                      |
| 2022 | 0.25%    | 2.25%                      |
| 2023 | 0.25%    | 2.25%                      |
| 2024 | 3.50%    | 5.50%                      |
| 2025 | 5.50%    | 7.50%                      |
| 2026 | 4.50%    | 6.50%                      |

Special Civil Part jurisdictional limit: **$20,000.00** (R. 6:1-2(a)(1);
N.J.S.A. 2A:6-43).

### Contact rules

| Setting                         | Value                                  | Source                                                  |
|---------------------------------|----------------------------------------|---------------------------------------------------------|
| Contact window (consumer-local) | 08:00 – 21:00                          | 15 U.S.C. § 1692c(a)(1); 12 C.F.R. § 1006.6(b)(1)       |
| Max telephone calls per day     | 1 attempt                              | Internal policy informed by 12 C.F.R. § 1006.14(b)      |
| Max telephone calls per 7 days  | 7 calls (7-in-7 rule)                  | 12 C.F.R. § 1006.14(b)(2)(i)                            |
| Validation notice deadline      | Within 5 days of initial communication | 15 U.S.C. § 1692g(a)                                    |
| Dispute response window         | 30 days from receipt of validation     | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38               |
| Consent to autodial / SMS       | Prior express written consent required | 47 U.S.C. § 227(b); 47 C.F.R. § 64.1200(f)(8)           |
| Email opt-out                   | Required reasonable/simple method      | 12 C.F.R. § 1006.6(d)(3)(i)                             |

### Statute of limitations

| Debt category    | Years | Statute                          |
|------------------|------:|----------------------------------|
| Written contract | 6     | N.J.S.A. 2A:14-1                 |
| Oral contract    | 6     | N.J.S.A. 2A:14-1                 |
| Open account     | 6     | N.J.S.A. 2A:14-1                 |
| Promissory note  | 6     | N.J.S.A. 2A:14-1 (UCC overlay)   |
| Domestic judgment| 20    | N.J.S.A. 2A:14-5 (renewable)     |

### Usury (defensive guard-rails)

NJ has broad licensed-lender exemptions; the values below are
guard-rail thresholds the system uses to flag rates for legal review.

| Debt category    | Civil cap | Criminal | Citation                                              |
|------------------|----------:|----------|-------------------------------------------------------|
| Written contract | 16.00%    | n/a      | N.J.S.A. 31:1-1(a)                                    |
| Open account     | 30.00%    | n/a      | N.J.S.A. 31:1-1(b) (broad licensed-lender exemptions) |
| Judgment         | 7.50%     | n/a      | R. 4:42-11(a) — guard rail only                       |

### Licensing and bonding

* Tenant must hold a valid NJ collection-agency registration where
  required (N.J.S.A. 45:18-1 et seq.; administered through the NJ
  Treasury Division of Revenue and Enterprise Services).
* Surety bond minimum: **$5,000** (N.J.S.A. 45:18-3). Stored on the pack
  as `default_bond_amount` (cents).
* When required documents are missing or expired the system flags the
  tenant non-compliant and blocks new outbound contact workflows
  (`engines.compliance.evaluate_contact_attempt` returns
  `BlockReason.LEGAL_HOLD` or `POLICY_PACK_MISSING` accordingly).

### Required notice templates

Templates live under `services/api/dcs_api/notices/templates/nj/` and are
registered in `dcs_api.notices.registry`:

| Key                          | Template ID                       | Authority                                              |
|------------------------------|-----------------------------------|--------------------------------------------------------|
| Initial communication notice | `nj.initial_communication`        | 15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e)          |
| Debt validation notice       | `nj.validation_notice`            | 12 C.F.R. § 1006.34 + Appendix B Model Form B-3        |
| Dispute acknowledgement      | `nj.dispute_acknowledgement`      | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d)           |
| Post-judgment disclosure     | `nj.post_judgment_disclosure`     | N.J. Court Rules, R. 4:42-11(a)                        |

Every render captures a SHA-256 `content_hash` written to the `notices`
table for defensibility (see `dcs_api.notices.renderer.render`).

### Required audit fields (snapshot on every calculation/notice)

* `policy_pack_id`
* `policy_pack_version`
* `source_snapshot_hashes`
* `rate_table_id` and `rate_table_version` (where applicable)
* `notice_template_id`, `notice_template_version`, `content_hash`
* `engine_version` (calculation engine semver — currently `1.1.0`)
