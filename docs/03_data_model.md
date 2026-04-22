## Core data model (v1)

This is the implemented core schema. SQLAlchemy models live under
`services/api/dcs_api/models/`; database migrations are under
`services/api/alembic/versions/`. All money is stored in **integer cents**;
all rates and intermediate math use `Decimal`.

### Tenant and security
* `Tenant` — multi-tenant isolation, business model, default jurisdiction.
* `User` — authentication, owner/master flags.
* `Role` / `Permission` / `RolePermission` / `UserRole` — RBAC.
* `AuditLog` — append-only, tamper-evident audit stream.

### Consumer and accounts
* `Consumer` — PII (name, SSN last-four, DOB), language preference, legal
  hold flag and reason.
* `ContactMethod` — phone / email / address with per-method suppression
  state.
* `Consent` — TCPA consent records (channel, scope, granted/revoked
  timestamps, source artifact reference).
* `SuppressionEntry` — opt-out / cease-and-desist / DNC entries; honored
  by `engines.compliance.evaluate_contact_attempt`.

### Debt and case lifecycle
* `Account` — balances (principal, interest, fees, total), status,
  jurisdiction, validation-notice tracking, legal hold flags.
* `Notice` — every outbound communication with template id, template
  version, channel, content hash (SHA-256), and delivery status.
* `Dispute` — dispute lifecycle; opening a dispute trips a legal hold.
* `Payment` / `PaymentAllocation` — payment capture and allocation rows.
* `Fee` — fee records with allowed-flag and jurisdiction citation.
* `Case` — workflow state, collector assignment.

### Litigation and judgments
* `LitigationCase` — court, docket, deadlines, status.
* `Judgment` — date, amount, threshold flag, policy pack snapshot.
* `JudgmentInterestAccrual` — daily/period accruals with rate-table
  pointer for defensibility.

### Compliance and rules
* `PolicyPack` — jurisdiction-scoped, versioned, with status lifecycle
  (DRAFT → ACTIVE → SUPERSEDED → ARCHIVED) and source registry.
* `RateTable` / `RateTableEntry` — annual interest-rate tables with
  optional threshold and above-threshold uplift.
* `StatuteOfLimitationsRule` — limitation period per debt category, with
  citation.
* `UsuryRule` — civil and criminal usury caps per debt category.

### Calculations
* `CalculationRequest` — inputs, engine version, requesting user,
  optional account/judgment pointers, plus pack/version snapshot.
* `CalculationResult` — outputs, step-by-step breakdown, rate-source
  citation, source snapshot hash, validity flag.

### Integrations
* `IdpConfig` — SAML / OIDC.
* `PaymentProcessorConfig` — Tratta tokenization references.
* `TelephonyConfig` — Vonage routing config.
* `EfilingConnectorConfig` — pluggable court connector adapters.

### Cross-cutting invariants

1. **Tenant scoping.** Every domain model except `PolicyPack` and
   `Permission` extends `TenantScopedModel`. A row is invisible outside
   the owning tenant by default.
2. **Append-only audit.** Mutations on retention-sensitive tables (notice,
   payment, calculation, audit_log, consent) emit an `AuditLog` row.
3. **Immutability of active packs.** `PolicyPack` rows in ACTIVE status
   may not be mutated by the seeder; bumping the version is required.
4. **No floats for money.** All currency is `Integer` (cents); all rates
   are `Numeric(8, 5)`; intermediate math uses `decimal.Decimal`.
