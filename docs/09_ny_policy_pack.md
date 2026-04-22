## NY policy pack (v2026.1)

This is the New York policy pack. Like NJ, it is versioned and attached
to every calculation, notice, and compliance decision. The seeded values
come from `services/api/scripts/seed_policy_packs.py`.

> **Non-legal guidance.** All citations and rates were captured from
> public materials and must be re-verified by qualified New York counsel
> before relying on the pack for production calculations or consumer-
> facing notices.

### Policy pack metadata

| Field            | Value                                       |
|------------------|---------------------------------------------|
| Jurisdiction     | NY                                          |
| Pack version     | `ny-2026.1`                                 |
| Effective start  | 2026-01-01                                  |
| Effective end    | open                                        |
| Status           | DRAFT (set ACTIVE via `--activate` flag)    |
| Source verification | Captured 2026; re-verify each year       |

### Source registry

| Key                          | Authority                         | Citation                                             |
|------------------------------|-----------------------------------|------------------------------------------------------|
| `fdcpa`                      | U.S. Congress                     | 15 U.S.C. § 1692 et seq.                             |
| `regulation_f`               | CFPB                              | 12 C.F.R. Part 1006                                  |
| `reg_f_validation`           | CFPB                              | 12 C.F.R. § 1006.34; Appendix B Model Form B-3       |
| `reg_f_call_frequency`       | CFPB                              | 12 C.F.R. § 1006.14(b)                               |
| `tcpa`                       | U.S. Congress / FCC               | 47 U.S.C. § 227; 47 C.F.R. § 64.1200                 |
| `ny_cplr_5004`               | New York State Legislature        | N.Y. C.P.L.R. § 5004(a)-(b)                          |
| `ny_consumer_credit_fairness_act` | New York State Legislature   | N.Y. C.P.L.R. § 214-i (eff. Apr. 7, 2022)            |
| `ny_cplr_213`                | New York State Legislature        | N.Y. C.P.L.R. § 213(2)                               |
| `ny_cplr_211`                | New York State Legislature        | N.Y. C.P.L.R. § 211(b)                               |
| `ny_gbl_29h`                 | New York State Legislature        | N.Y. Gen. Bus. Law Art. 29-H, §§ 600 – 603-d         |
| `nyc_dcwp_licensing`         | NYC DCWP                          | NYC Admin. Code Title 20, Subch. 30; 6 RCNY § 2-191  |

URLs persisted in the JSON registry:

* NY Senate / Laws (CPLR & GBL): `https://www.nysenate.gov/legislation/laws`
* NYC DCWP debt-collection licensing:
  `https://www.nyc.gov/site/dca/businesses/license-checklist-debt-collection-agency.page`
* CFPB Reg F: `https://www.consumerfinance.gov/rules-policy/regulations/1006/`

### Post-judgment interest

| Type           | Annual rate | Authority                                                      |
|----------------|------------:|----------------------------------------------------------------|
| Default        | 9.00%       | N.Y. C.P.L.R. § 5004(a)                                        |
| Consumer debt  | 2.00%       | N.Y. C.P.L.R. § 5004(b) (effective Apr. 30, 2022)              |

* The default rate applies to all judgments not arising from a "consumer
  debt" as defined in N.Y. C.P.L.R. § 105(f).
* The consumer-debt rate applies to any judgment "arising out of a
  consumer credit transaction" as defined in § 105(f-1) and is
  prospectively applied for accruals on/after Apr. 30, 2022.
* Day count: actual/365, simple interest. The calculation engine prorates
  daily across calendar-year boundaries
  (`engines.calculation.calculate_post_judgment_interest`).

### Contact rules

| Setting                         | Value                                  | Source                                        |
|---------------------------------|----------------------------------------|-----------------------------------------------|
| Contact window (consumer-local) | 08:00 – 21:00                          | 15 U.S.C. § 1692c(a)(1); 12 C.F.R. § 1006.6   |
| Max telephone calls per day     | 1 attempt                              | Internal (informed by 12 C.F.R. § 1006.14(b)) |
| Max telephone calls per 7 days  | 7 calls                                | 12 C.F.R. § 1006.14(b)(2)(i)                  |
| Validation notice deadline      | Within 5 days of initial communication | 15 U.S.C. § 1692g(a)                          |
| Dispute response window         | 30 days                                | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38     |
| Consent for autodial / SMS      | Prior express written consent          | 47 U.S.C. § 227(b); 47 C.F.R. § 64.1200       |

### Statute of limitations

| Debt category         | Years | Statute                                                                  |
|-----------------------|------:|--------------------------------------------------------------------------|
| Written contract      | 6     | N.Y. C.P.L.R. § 213(2)                                                   |
| Open account (consumer) | 3   | N.Y. C.P.L.R. § 214-i (Consumer Credit Fairness Act, eff. Apr. 7, 2022)  |
| Promissory note       | 6     | N.Y. C.P.L.R. § 213(2) (UCC overlay where applicable)                    |
| Money judgment        | 20    | N.Y. C.P.L.R. § 211(b)                                                   |

The CCFA also bars revival of a time-barred consumer debt by partial
payment. The validation notice template (`ny.validation_notice`)
includes the required SOL disclosure (CPLR § 214-i).

### Usury (defensive guard-rails)

| Debt category    | Civil cap | Criminal cap | Authority                                          |
|------------------|----------:|-------------:|----------------------------------------------------|
| Written contract | 16.00%    | 25.00%       | N.Y. Gen. Oblig. Law § 5-501; N.Y. Penal Law § 190.40 |
| Judgment         | 9.00%     | n/a          | CPLR § 5004(a) (consumer judgments capped at 2% by § 5004(b)) |

### Licensing and bonding

* New York State does not impose a single statewide collection-agency
  bond, but **NYC DCWP licensing** is required for any agency collecting
  from NYC consumers (NYC Admin. Code Title 20, Subch. 30; 6 RCNY
  § 2-191 et seq.). Bond and disclosure rules are tracked in the planned
  `nyc-2026.1` sub-pack.
* NY GBL Article 29-H imposes registration requirements for
  out-of-state debt collectors collecting from NY consumers
  (§§ 600 – 603-d).

### Required notice templates

Templates live under `services/api/dcs_api/notices/templates/ny/`:

| Key                          | Template ID                       | Authority                                           |
|------------------------------|-----------------------------------|-----------------------------------------------------|
| Initial communication notice | `ny.initial_communication`        | 15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e); CCFA  |
| Debt validation notice       | `ny.validation_notice`            | 12 C.F.R. § 1006.34 + Appendix B; CPLR § 214-i      |
| Dispute acknowledgement      | `ny.dispute_acknowledgement`      | 15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d)        |
| Post-judgment disclosure     | `ny.post_judgment_disclosure`     | N.Y. C.P.L.R. § 5004(a)-(b); § 211(b)               |

### Open / future work for NY

* **NYC DCWP sub-pack** (`nyc-2026.1`) — incorporate the additional NYC
  language disclosure, written-validation requirements, and
  language-access rules under 6 RCNY § 2-191 et seq.
* **Verify the consumer-debt definition** in CPLR § 105(f-1) against
  edge-case account types (medical, telecom, utilities) before applying
  the 2% rate by default.
* **Surety/registration tracking** for GBL Art. 29-H — current pack
  flags but does not auto-block on missing registration.
