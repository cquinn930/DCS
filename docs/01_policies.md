## Policy defaults

These policies are defaults to keep the platform compliant and defensible. They are configurable per tenant unless marked as non-delegable.

### Acceptable Use Policy (AUP)
Forbidden actions (system-enforced):
- Contact outside permitted hours or contact cadence for the jurisdiction.
- Harassing or repeated contact beyond configured limits.
- Misrepresentation of identity, authority, or legal status.
- Disclosure of debt information to unauthorized third parties.
- Threats of arrest, violence, or actions not legally authorized.
- Contacting a consumer at work after notice to stop.
- Ignoring dispute flags or legal hold states.

Required behaviors:
- All communications must use approved templates.
- Each contact must be linked to a consent record or lawful basis.
- Opt-out must be honored immediately across all channels.

### TCPA / consent rules (defaults)
- Consent is required for autodialed calls and SMS.
- Consent must be explicit and recorded with timestamp, source, and scope (channel, phone number).
- Revocation is immediate; suppression lists are applied across all outbound channels.
- Consent cannot be inferred from prior payments or account ownership.
- Consent is tenant-configurable by channel, but cannot be disabled.

### Data retention and deletion
- Default retention: 7 years after account closure or final activity, whichever is later.
- Audit logs, payment records, notices, and consent records are immutable.
- Owner may adjust retention up or down, but not below statutory minimums per state.

### Legal hold
Legal hold automatically applies to:
- Dispute opened.
- Litigation initiated.
- Bankruptcy notice received.
- Regulatory inquiry or subpoena.

Legal hold prevents:
- Deletion or anonymization of records.
- Balance adjustments without explicit approval and audit notes.

### Breach response and lockdown
Default actions on breach detection:
- Notify all owners, admins, and supervisors immediately.
- Enter lockdown state: no data changes, no outbound communications, read-only access.
- Only owner (or master account) can lift lockdown.
- Master account actions are fully audited and visible to tenant owners.

### Non-delegable permissions (owner only)
- Modify retention policy below 7 years.
- Disable mandatory consent tracking.
- Disable audit logging.
- Unlock breach lockdown.
