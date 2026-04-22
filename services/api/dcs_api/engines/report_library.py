"""Pre-built report template library.

Provides standard collection industry report definitions that can be
seeded into a tenant's report templates on first setup.
"""

STANDARD_REPORTS: list[dict] = [
    # ---- Client / Placement Reports ----
    {
        "name": "Client Referral Summary",
        "description": "Accounts placed by client with balance and status breakdown",
        "report_type": "summary",
        "source_entity": "accounts",
        "columns": [
            {"field": "original_creditor", "label": "Client"},
            {"field": "id", "label": "Account Count", "aggregate": "count"},
            {"field": "original_principal", "label": "Original Principal", "aggregate": "sum"},
            {"field": "total_balance", "label": "Current Balance", "aggregate": "sum"},
        ],
        "group_by": ["original_creditor"],
        "sort": [{"field": "original_creditor", "direction": "asc"}],
        "is_system": True,
        "category": "client",
    },
    {
        "name": "Placement Analysis by State",
        "description": "Account placement and collection data grouped by jurisdiction",
        "report_type": "summary",
        "source_entity": "accounts",
        "columns": [
            {"field": "jurisdiction", "label": "State"},
            {"field": "id", "label": "Total Accounts", "aggregate": "count"},
            {"field": "original_principal", "label": "Placed Amount", "aggregate": "sum"},
            {"field": "total_balance", "label": "Outstanding", "aggregate": "sum"},
        ],
        "group_by": ["jurisdiction"],
        "sort": [{"field": "jurisdiction", "direction": "asc"}],
        "is_system": True,
        "category": "client",
    },
    {
        "name": "Client Fee Breakdown",
        "description": "Fees assessed per client with type breakdown",
        "report_type": "tabular",
        "source_entity": "accounts",
        "columns": [
            {"field": "original_creditor", "label": "Client"},
            {"field": "account_reference", "label": "Account"},
            {"field": "current_fees", "label": "Fees"},
            {"field": "total_balance", "label": "Balance"},
        ],
        "filters": [{"field": "current_fees", "operator": "gt", "value": 0}],
        "sort": [{"field": "original_creditor", "direction": "asc"}],
        "is_system": True,
        "category": "client",
    },

    # ---- Financial Reports ----
    {
        "name": "Collections Summary",
        "description": "Total collections received by payment method and status",
        "report_type": "summary",
        "source_entity": "payments",
        "columns": [
            {"field": "method", "label": "Payment Method"},
            {"field": "id", "label": "Count", "aggregate": "count"},
            {"field": "amount", "label": "Total Amount", "aggregate": "sum"},
        ],
        "group_by": ["method"],
        "filters": [{"field": "status", "operator": "eq", "value": "completed"}],
        "is_system": True,
        "category": "financial",
    },
    {
        "name": "End of Day Totals",
        "description": "Payments received today grouped by method",
        "report_type": "summary",
        "source_entity": "payments",
        "columns": [
            {"field": "method", "label": "Method"},
            {"field": "id", "label": "Transactions", "aggregate": "count"},
            {"field": "amount", "label": "Amount", "aggregate": "sum"},
        ],
        "group_by": ["method"],
        "parameters": [{"name": "date", "type": "date", "required": True}],
        "is_system": True,
        "category": "financial",
    },
    {
        "name": "Payment Allocation Detail",
        "description": "How payments were allocated across principal, interest, fees, and costs",
        "report_type": "tabular",
        "source_entity": "payments",
        "columns": [
            {"field": "account_id", "label": "Account"},
            {"field": "amount", "label": "Payment"},
            {"field": "method", "label": "Method"},
            {"field": "status", "label": "Status"},
            {"field": "received_at", "label": "Received"},
        ],
        "sort": [{"field": "received_at", "direction": "desc"}],
        "is_system": True,
        "category": "financial",
    },

    # ---- Performance / Collector Reports ----
    {
        "name": "Collector Performance Summary",
        "description": "Accounts worked, payments secured, and amounts collected per collector",
        "report_type": "summary",
        "source_entity": "users",
        "columns": [
            {"field": "email", "label": "Collector"},
            {"field": "first_name", "label": "First Name"},
            {"field": "last_name", "label": "Last Name"},
        ],
        "is_system": True,
        "category": "performance",
    },

    # ---- Aging Reports ----
    {
        "name": "Account Aging by Status",
        "description": "Account balances grouped by current status",
        "report_type": "summary",
        "source_entity": "accounts",
        "columns": [
            {"field": "status", "label": "Status"},
            {"field": "id", "label": "Count", "aggregate": "count"},
            {"field": "total_balance", "label": "Total Balance", "aggregate": "sum"},
            {"field": "current_principal", "label": "Principal", "aggregate": "sum"},
            {"field": "current_interest", "label": "Interest", "aggregate": "sum"},
        ],
        "group_by": ["status"],
        "is_system": True,
        "category": "aging",
    },
    {
        "name": "Account Aging by Debt Type",
        "description": "Balance aging grouped by type of debt",
        "report_type": "summary",
        "source_entity": "accounts",
        "columns": [
            {"field": "debt_type", "label": "Debt Type"},
            {"field": "id", "label": "Count", "aggregate": "count"},
            {"field": "original_principal", "label": "Original", "aggregate": "sum"},
            {"field": "total_balance", "label": "Current", "aggregate": "sum"},
        ],
        "group_by": ["debt_type"],
        "is_system": True,
        "category": "aging",
    },

    # ---- Compliance Reports ----
    {
        "name": "Overdue Dispute Responses",
        "description": "Disputes where response_due_date has passed without resolution",
        "report_type": "tabular",
        "source_entity": "disputes",
        "columns": [
            {"field": "id", "label": "Dispute ID"},
            {"field": "account_id", "label": "Account"},
            {"field": "reason", "label": "Reason"},
            {"field": "status", "label": "Status"},
            {"field": "filed_at", "label": "Filed"},
            {"field": "response_due_date", "label": "Due"},
        ],
        "filters": [
            {"field": "status", "operator": "in", "value": ["pending", "under_review"]},
        ],
        "sort": [{"field": "response_due_date", "direction": "asc"}],
        "is_system": True,
        "category": "compliance",
    },
    {
        "name": "Validation Notice Tracking",
        "description": "Accounts and their validation notice status",
        "report_type": "tabular",
        "source_entity": "accounts",
        "columns": [
            {"field": "account_reference", "label": "Account"},
            {"field": "original_creditor", "label": "Client"},
            {"field": "validation_notice_sent", "label": "Sent"},
            {"field": "validation_notice_date", "label": "Date Sent"},
            {"field": "date_placed", "label": "Placed"},
        ],
        "sort": [{"field": "date_placed", "direction": "desc"}],
        "is_system": True,
        "category": "compliance",
    },
    {
        "name": "Legal Hold Inventory",
        "description": "All accounts currently under legal hold",
        "report_type": "tabular",
        "source_entity": "accounts",
        "columns": [
            {"field": "account_reference", "label": "Account"},
            {"field": "original_creditor", "label": "Client"},
            {"field": "total_balance", "label": "Balance"},
            {"field": "legal_hold_reason", "label": "Reason"},
            {"field": "legal_hold_date", "label": "Hold Date"},
        ],
        "filters": [{"field": "legal_hold", "operator": "eq", "value": True}],
        "sort": [{"field": "legal_hold_date", "direction": "desc"}],
        "is_system": True,
        "category": "compliance",
    },
    {
        "name": "TCPA Consent Status",
        "description": "Consumer consent records by channel and status",
        "report_type": "tabular",
        "source_entity": "consumers",
        "columns": [
            {"field": "first_name", "label": "First Name"},
            {"field": "last_name", "label": "Last Name"},
            {"field": "external_id", "label": "External ID"},
        ],
        "is_system": True,
        "category": "compliance",
    },

    # ---- Litigation Reports ----
    {
        "name": "Litigation Case Inventory",
        "description": "All open litigation cases with court and status information",
        "report_type": "tabular",
        "source_entity": "litigation_cases",
        "columns": [
            {"field": "account_id", "label": "Account"},
            {"field": "court_name", "label": "Court"},
            {"field": "docket_number", "label": "Docket"},
            {"field": "status", "label": "Status"},
            {"field": "principal_claimed", "label": "Principal"},
            {"field": "filed_date", "label": "Filed"},
        ],
        "sort": [{"field": "filed_date", "direction": "desc"}],
        "is_system": True,
        "category": "litigation",
    },
    {
        "name": "Judgment Inventory",
        "description": "All judgments with accrued interest and satisfaction status",
        "report_type": "tabular",
        "source_entity": "judgments",
        "columns": [
            {"field": "litigation_case_id", "label": "Case"},
            {"field": "judgment_amount", "label": "Amount"},
            {"field": "total_accrued_interest", "label": "Accrued Interest"},
            {"field": "post_judgment_rate", "label": "Rate"},
            {"field": "judgment_date", "label": "Date"},
            {"field": "satisfaction_recorded", "label": "Satisfied"},
        ],
        "sort": [{"field": "judgment_date", "direction": "desc"}],
        "is_system": True,
        "category": "litigation",
    },

    # ---- Operational Reports ----
    {
        "name": "Account Status Distribution",
        "description": "Count and balance of accounts in each status",
        "report_type": "summary",
        "source_entity": "accounts",
        "columns": [
            {"field": "status", "label": "Status"},
            {"field": "id", "label": "Count", "aggregate": "count"},
            {"field": "total_balance", "label": "Balance", "aggregate": "sum"},
            {"field": "original_principal", "label": "Original", "aggregate": "sum"},
        ],
        "group_by": ["status"],
        "is_system": True,
        "category": "operational",
    },
    {
        "name": "Audit Trail",
        "description": "Recent audit log entries",
        "report_type": "tabular",
        "source_entity": "audit_logs",
        "columns": [
            {"field": "action", "label": "Action"},
            {"field": "entity_type", "label": "Entity"},
            {"field": "description", "label": "Description"},
            {"field": "user_id", "label": "User"},
            {"field": "created_at", "label": "Timestamp"},
        ],
        "sort": [{"field": "created_at", "direction": "desc"}],
        "is_system": True,
        "category": "operational",
    },
]


def get_standard_report_definitions() -> list[dict]:
    """Return all standard report definitions for seeding."""
    return STANDARD_REPORTS
