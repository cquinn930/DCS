## DCS product overview

DCS is a multi-tenant debt-collection platform. It captures, services, and
litigates consumer and commercial debt while enforcing federal and
state-by-state compliance rules.

### Business scope
* Customers: collection agencies, law firms, in-house collections, and
  debt buyers.
* Debt types: consumer, commercial, medical, judgments.
* Jurisdiction packs: **New Jersey** (`nj-2026.1`) and **New York**
  (`ny-2026.1`) shipped; additional state packs added per
  `09_ny_policy_pack.md`-style templates.
* Business model: SaaS subscription with optional per-tenant modes
  (per-account, contingency, debt-buyer).

### Compliance posture (software-only)
* DCS is a software platform. Tenants are the regulated debt collectors;
  DCS provides the controls that help them comply. Non-legal guidance:
  the platform does not guarantee compliance — qualified counsel must
  review tenant configuration.
* PCI scope is minimized via Tratta tokenization; the platform does not
  store PAN unless a tenant explicitly opts in.
* Data residency: single region at launch, multi-cloud-ready
  architecture.

### Default product scope
* Inbound consumer portal: disputes and payments
  (`docs/04_workflows.md`).
* Outbound communications: voice, SMS, email, letter — all gated by
  `engines.compliance.evaluate_contact_attempt`
  (FDCPA § 1692c(a)(1) hours, Reg F § 1006.14(b) 7-in-7, TCPA consent,
  suppression list).
* Litigation support: case management, judgments, post-judgment interest
  per state pack, e-filing connector layer.
* RBAC: collector, supervisor, legal reviewer, admin, owner, plus custom
  roles (`docs/05_rbac.md`).
* Audit logging: immutable, append-only, exportable, tamper-evident.

### Controls delivered

* **Policy packs** — `models/compliance.py`, seeded by
  `services/api/scripts/seed_policy_packs.py`.
* **Compliance engine** — `engines/compliance.py`
  (contact-rule evaluator, consent/suppression/legal-hold checks, SOL
  evaluator, usury validator).
* **Calculation engine** — `engines/calculation.py`
  (simple/compound interest, NJ R. 4:42-11(a) post-judgment, NY CPLR
  § 5004(a)/(b) post-judgment, payment allocation).
* **Notice templates + renderer** — `notices/registry.py`,
  `notices/renderer.py`, with four required templates per state
  (initial communication, validation, dispute acknowledgement,
  post-judgment disclosure).
* **CollectMax migration tooling** — `migration/migrate_collectmax.py`
  and helpers, to onboard existing FLG data.

### Open items intentionally deferred

* **NYC sub-pack** (NYC DCWP licensing under NYC Admin. Code Title 20,
  Subch. 30; 6 RCNY § 2-191 et seq.) — out of scope for v1; planned as a
  child pack of `ny-2026.1`.
* **Additional state packs** beyond NJ/NY — planned per the same shape
  used in `nj-2026.1` and `ny-2026.1`.
* **Specific NJ/NY court e-filing endpoints** — connector interface
  exists (`integrations`); endpoint configuration completed per court
  during onboarding.
* **Client-by-client overrides** — defaults live on `PolicyPack`; tenant-
  and client-level overrides extend by config rather than code change.
