## Integrations (defaults)

### Identity providers
- Support SAML 2.0 and OIDC (cloud providers only).
- Supported IdPs: Azure AD (cloud), Okta, and generic OIDC/SAML.
- LDAP/ADFS: cloud-only via provider connectors (no on-prem).

### Payments (Tratta)
- Use tokenization and hosted/embedded checkout where possible.
- Store processor references only; avoid PAN storage by default.
- Support card + ACH + eCheck if available.

### Telephony/SMS (Vonage)
- Outbound voice and SMS via Vonage APIs.
- Call recording optional and consent-gated.
- Suppression list and opt-out integrated at send time.

### Court e-filing / case systems
- Implement a connector interface with pluggable adapters.
- Default workflow supports document generation, submission, and status polling.
- Specific NJ and NY endpoints to be configured later.
