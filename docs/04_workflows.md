## Core workflows (defaults)

### Inbound consumer portal: dispute
1. Consumer submits dispute with reason and documents.
2. System creates Dispute record and applies legal hold.
3. Validation notice workflow triggers with jurisdiction-specific timelines.
4. Collector/legal reviewer responds; resolution captured with audit notes.

### Inbound consumer portal: payment
1. Consumer selects payment method (Tratta tokenized).
2. Payment captured; allocation applied per tenant rule.
3. Receipt and statement generated; audit log recorded.

### Outbound contact (calls/email/SMS)
1. Contact attempt created with consent check and suppression validation.
2. Communication routed via Vonage (voice/SMS) or email provider.
3. Call recording and transcript stored if enabled.
4. Opt-out updates suppression lists immediately.

### Litigation support
1. Case created with court metadata and deadlines.
2. Judgment entered with policy pack and rate snapshot.
3. Post-judgment interest accrues daily based on NJ rules.
4. E-filing connector prepares and submits filings (when configured).
