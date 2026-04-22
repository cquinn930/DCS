"""DCS processing engines.

- reporting: Dynamic query builder and report output formatter
- importing: File parsing and data import processor
- exporting: Data export with format transforms
- scripting: Safe sandboxed DSL interpreter (DCS Script)
- workflow: Activity processing, chain execution
- documents: Template merge field resolution and rendering
- automation: Event rule evaluation, DB-driven job scheduler
- credit_reporting: Metro II bureau batch generation
- reconciliation: Bank statement import and auto-matching
- compliance: Policy-pack-driven contact/consent/hold/SOL rule evaluator
              (FDCPA, Reg F, TCPA, NJ Title 2A:14, NY CPLR § 213/214-i, etc.)
- calculation: Decimal-safe interest / post-judgment / payment-allocation math
               backed by the active policy pack rate tables
                (NJ R. 4:42-11(a), NY CPLR § 5004(a)/(b))
"""
