## Notice templates

Every consumer-facing notice the platform sends is rendered from a
versioned template under
`services/api/dcs_api/notices/templates/<jurisdiction>/`. Templates are
plain text with `${field}` placeholders so they are easy to audit and
have no runtime code-execution surface (no Jinja, no eval, no JS).

The renderer (`dcs_api.notices.renderer.render`) returns a
`RenderedNotice` carrying:

* `body` — the substituted text, ready for delivery channel rendering;
* `content_hash` — SHA-256 of `body`, written to `notices.content_hash`
  so the exact text mailed/emailed can be reconstructed and proven during
  a regulatory audit;
* `missing_fields` — list of required fields the caller did not supply
  (rendered as `(not provided)` or `$0.00` so the operator notices).

### Catalog

| Template ID                       | Jurisdiction | Purpose                                         | Authority                                                       |
|-----------------------------------|--------------|-------------------------------------------------|-----------------------------------------------------------------|
| `nj.initial_communication`        | NJ           | First contact "this is a debt collector" notice  | 15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e)                   |
| `nj.validation_notice`            | NJ           | Reg F validation information                    | 12 C.F.R. § 1006.34 + Appendix B Model Form B-3                 |
| `nj.dispute_acknowledgement`      | NJ           | Acknowledge consumer dispute, pause collection  | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d)                    |
| `nj.post_judgment_disclosure`     | NJ           | Post-judgment interest accrual disclosure       | N.J. Court Rules, R. 4:42-11(a)                                 |
| `ny.initial_communication`        | NY           | First contact + NY CCFA SOL overlay              | 15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e); CPLR § 214-i      |
| `ny.validation_notice`            | NY           | Reg F validation + NY consumer-credit SOL block | 12 C.F.R. § 1006.34 + Appendix B; CPLR § 214-i                  |
| `ny.dispute_acknowledgement`      | NY           | Acknowledge dispute, pause collection           | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d); GBL Art. 29-H     |
| `ny.post_judgment_disclosure`     | NY           | Post-judgment disclosure (CPLR § 5004(a)/(b))   | N.Y. C.P.L.R. § 5004(a)-(b); § 211(b)                           |

All templates are version `2026.1`. Bumping the version creates a new
template row; old renders retain their original version + content hash
for audit reconstruction.

### Required merge fields by template

The registry pins required fields per template
(`registry._VALIDATION_REQUIRED_FIELDS` etc.). If any required field is
missing at render time it is recorded in `RenderedNotice.missing_fields`
so the API or batch job can reject the send rather than mail an
incomplete notice. The five field groups:

* **Validation notice** — full Reg F § 1006.34(c) information block:
  current creditor, original creditor, account number last-four,
  itemization date, principal/interest/fees/payments/credits buckets,
  current balance, dispute deadline (30 days), tenant contact info, and
  state disclosure.
* **Initial communication** — tenant identity, consumer name, current
  creditor, current balance, miniranda disclosure, tenant contact info.
* **Dispute acknowledgement** — consumer info, dispute received date,
  dispute summary, verification window (default 30 days), next steps.
* **Post-judgment disclosure** — court, docket, judgment date and
  amount, current principal, accrued interest, applied rate and source
  citation, above-threshold flag.

### Rendering example

```python
from dcs_api.notices import load_template, render

tpl = load_template("NJ", "nj.validation_notice")
notice = render(tpl, {
    "tenant_legal_name": "Faloni Law Group LLC",
    "tenant_address": "165 Passaic Ave, Fairfield, NJ 07004",
    "tenant_phone": "(973) 277-1144",
    "tenant_email": "info@falonilaw.com",
    "today_date": today,
    "consumer_full_name": consumer.full_name(),
    "consumer_address": consumer.mailing_address(),
    "account_reference": account.account_reference,
    "account_number_last_four": account.client_account_number[-4:],
    "current_creditor_name": account.current_creditor or account.original_creditor,
    "original_creditor_name": account.original_creditor,
    "validation_period_start": account.itemization_date,
    "itemization_principal_cents": account.original_principal,
    "itemization_interest_cents":  account.itemization_interest,
    "itemization_fees_cents":      account.itemization_fees,
    "itemization_payments_cents":  account.itemization_payments,
    "itemization_credits_cents":   account.itemization_credits,
    "current_balance_cents":       account.total_balance,
    "dispute_deadline_date":       today + timedelta(days=30),
    "state_disclosure": "...",
})

assert not notice.missing_fields, notice.missing_fields
db_notice.template_id = notice.template_id
db_notice.template_version = notice.template_version
db_notice.content_hash = notice.content_hash
```

### Authoring guidelines

1. Use **plain ASCII** where possible. Avoid smart quotes and en-dashes
   that look fine in editors but render poorly in DOS print queues.
2. Use the `${field_cents}` convention for any monetary value; the
   renderer will add a parallel `${field_formatted}` ($1,234.56). Always
   reference the formatted variant in the visible body.
3. Cite the controlling statute / rule **inside the visible body** so
   consumer counsel can audit the basis for the disclosure.
4. End every template with a "Non-legal guidance:" disclaimer. The
   platform is software, not a law firm.
5. When adding a new template, register it in
   `dcs_api/notices/registry.py` *and* attach it to the relevant policy
   pack via `policy_packs.notice_templates` so the active pack
   advertises it.
