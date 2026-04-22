## New Jersey compliance truth set

This is the legal "truth set" for New Jersey, captured into the active
policy pack (`nj-2026.1` — see `08_nj_policy_pack.md`). Each source below
is registered with a citation and a public URL on `policy_packs.sources`
so audit logs can resolve which authority controlled a given decision.

> **Non-legal guidance.** Citations and rates were captured from public
> materials and must be re-verified by qualified New Jersey counsel
> before relying on them in production.

### Primary sources (verified and stored on `nj-2026.1`)

| # | Source                                                              | Citation                                              |
|---|---------------------------------------------------------------------|-------------------------------------------------------|
| 1 | Fair Debt Collection Practices Act                                  | 15 U.S.C. § 1692 et seq.                              |
| 2 | CFPB Regulation F                                                   | 12 C.F.R. Part 1006                                   |
| 3 | Reg F validation information requirements                           | 12 C.F.R. § 1006.34; Appendix B Model Form B-3        |
| 4 | Reg F 7-in-7 telephone-call frequency                               | 12 C.F.R. § 1006.14(b)(2)(i)                          |
| 5 | TCPA — consent for autodialed/text contacts                         | 47 U.S.C. § 227; 47 C.F.R. § 64.1200                  |
| 6 | NJ post-judgment interest rule                                      | N.J. Court Rules, R. 4:42-11(a)                       |
| 7 | NJ AOC annual Notice to the Bar (post-judgment rates)               | Administrative Office of the Courts (annual; January) |
| 8 | NJ Special Civil Part jurisdictional limit ($20,000)                | R. 6:1-2(a)(1); N.J.S.A. 2A:6-43                      |
| 9 | NJ statute of limitations — contracts and open accounts (6 years)   | N.J.S.A. 2A:14-1                                      |
|10 | NJ statute of limitations — domestic judgment (20 years; renewable) | N.J.S.A. 2A:14-5                                      |
|11 | NJ Collection Agencies Act (licensing)                              | N.J.S.A. 45:18-1 et seq.                              |
|12 | NJ Collection Agencies — surety bond minimum ($5,000)               | N.J.S.A. 45:18-3                                      |
|13 | NJ Consumer Fraud Act (overlay; treble damages)                     | N.J.S.A. 56:8-1 et seq.                               |

### Minimum enforcement features (implemented)

* **Post-judgment interest** based on judgment date, $20,000 SCP threshold,
  and the AOC annual notice rate
  (`engines.calculation.calculate_post_judgment_interest`).
* **Above-threshold uplift** of +2.0 percentage points
  (`policy_pack.rate_tables[POST_JUDGMENT_STANDARD].above_threshold_adjustment`).
* **Licensing/bond tracking** via `tenants.compliance_documents` (bond
  default $5,000); non-compliant tenants are blocked by
  `engines.compliance.evaluate_contact_attempt` returning
  `BlockReason.LEGAL_HOLD`.
* **Validation notice timeline** (5-day deliver / 30-day dispute window)
  enforced by `engines.compliance.evaluate_account_compliance` and the
  notice templates.
* **Dispute workflow** — opening a dispute applies a legal hold via
  `engines.compliance.apply_legal_hold` and trips
  `BlockReason.DISPUTE_OPEN` until verification completes
  (12 C.F.R. § 1006.38(d); 15 U.S.C. § 1692g(b)).
* **Contact-hour and call-frequency caps**
  (Reg F § 1006.6(b)(1) + § 1006.14(b)) enforced by
  `engines.compliance.evaluate_contact_attempt`.

### Policy pack versioning requirements

Each policy pack persists:

* Effective date range (`effective_start`, `effective_end`)
* Source URLs and PDF snapshot hashes (in `sources` JSONB)
* Rate tables with per-year entries
* Notice template registry references (`notice_templates`)
* Contact and communication limits
* Licensing/bond requirements

Every calculation and notice writes the pack id, pack version, rate-table
id, and snapshot hash into its audit row so the controlling authority
can be reconstructed from any historical record.
