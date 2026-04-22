## Calculation engine (defaults)

### Supported interest types
- Simple daily interest.
- Compound interest (daily, monthly, annually).
- Post-judgment interest (jurisdiction rules).

### Inputs
- principal (currency)
- interest_rate (annual percent)
- interest_type (simple, compound, post_judgment)
- compounding_frequency (daily, monthly, annually)
- start_date, end_date (defined inclusive/exclusive per policy)
- rounding_rule (final-step or stepwise)
- payments (date, amount)
- fees (type, amount, jurisdiction validation)

### Formulas (defaults)
Simple daily interest:
- daily_rate = (annual_rate / 100) / 365
- interest = principal * daily_rate * days

Compound interest:
- r = annual_rate / 100
- amount = principal * (1 + r/n) ** (n * years)
- interest = amount - principal

Post-judgment interest:
- rate determined by jurisdiction pack and threshold rules
- daily accrual as simple daily interest

### Payment allocation (default)
- Apply payments to interest first, then principal, then fees.
- Tenant can configure allocation order unless jurisdiction forbids changes.

### Versioning and defensibility
- Store input snapshot + calculation engine version + policy pack version.
- Store rate source (name, URL, effective date).
- Store statute or notice PDF hash for legal defensibility.

### Edge cases
- Leap years and day-count conventions.
- Returned or reversed payments.
- Settlement adjustments.
- Interest caps and usury limits per state.
