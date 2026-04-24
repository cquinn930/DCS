"""Database models for DCS.

Organized by domain:
- tenant: Multi-tenancy and security
- consumer: Consumer records and contact methods
- account: Debt accounts and instruments
- litigation: Cases, judgments, and interest
- compliance: Policy packs and rules
- calculation: Interest and payment calculations
- customization: Reports, imports, exports, scripting
- workflow: Activities, work queues, chains
- trust: Trust accounting and bank reconciliation
- documents: Document templates and generation
- automation: Event rules and job scheduler
- tags: Account tagging system
- performance: Collector goals and metrics
- credit_reporting: Bureau reporting (Metro II)
- edi: Electronic data interchange
- skip_trace: Skip tracing vendor integration
- masking: Data privacy and field masking
- waterfall: Payment allocation rules
- costs: Cost tracking and billing
"""

from dcs_api.models.tenant import (
    AuditLog,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from dcs_api.models.consumer import (
    Consent,
    Consumer,
    ContactMethod,
    SuppressionEntry,
)
from dcs_api.models.account import (
    Account,
    Case,
    DebtInstrument,
    Dispute,
    Fee,
    Notice,
    Payment,
    PaymentAllocation,
)
from dcs_api.models.litigation import (
    Judgment,
    JudgmentInterestAccrual,
    LitigationCase,
)
from dcs_api.models.compliance import (
    PolicyPack,
    RateTable,
    RateTableEntry,
    StatuteOfLimitationsRule,
    UsuryRule,
)
from dcs_api.models.calculation import (
    CalculationRequest,
    CalculationResult,
)
from dcs_api.models.customization import (
    ExportJob,
    ExportTemplate,
    ImportJob,
    ImportTemplate,
    ReportExecution,
    ReportTemplate,
    Script,
    ScriptExecution,
)
from dcs_api.models.workflow import (
    ActivityCode,
    ActivityEntry,
    QueueEntry,
    WorkflowChain,
    WorkflowChainStep,
    WorkQueue,
)
from dcs_api.models.trust import (
    BankReconciliation,
    ReconciliationItem,
    TrustAccount,
    TrustTransaction,
)
from dcs_api.models.documents import (
    DocumentBatch,
    DocumentGeneration,
    DocumentTemplate,
)
from dcs_api.models.automation import (
    EventLog,
    EventRule,
    JobExecution,
    ScheduledJob,
)
from dcs_api.models.tags import (
    TagAssignment,
    TagDefinition,
)
from dcs_api.models.performance import (
    CollectorGoal,
    GoalGroup,
    PerformanceSnapshot,
)
from dcs_api.models.credit_reporting import (
    BureauBatch,
    BureauConfig,
    BureauRecord,
)
from dcs_api.models.edi import (
    DataExchangeBatch,
    DataExchangeFormat,
    DataExchangePartner,
)
from dcs_api.models.skip_trace import (
    SkipTraceRequest,
    SkipTraceResult,
)
from dcs_api.models.masking import MaskingPolicy
from dcs_api.models.waterfall import (
    PaymentWaterfall,
    WaterfallRule,
)
from dcs_api.models.costs import (
    CostBilling,
    CostDisbursement,
    CostEntry,
)
from dcs_api.models.remittance import (
    RemittanceConfig,
    RemittanceLineItem,
    RemittanceStatement,
)
from dcs_api.models.flash_messages import (
    AccountFlashMessage,
    FlashMessageTemplate,
)
from dcs_api.models.reviews import (
    AccountReview,
    AccountReviewItem,
    ReviewTemplate,
    ReviewTemplateItem,
)
from dcs_api.models.courts import (
    Court,
    CourtCostOverride,
    CourtRepresentative,
)
from dcs_api.models.payment_plans import (
    PaymentPlan,
    ScheduledPayment,
)
from dcs_api.models.batch_letters import (
    BatchLetterConfig,
    BatchLetterRule,
)
from dcs_api.models.subplans import (
    SubPlan,
    SubPlanStep,
)
from dcs_api.models.audit import (
    AccountAccessLog,
    AuditConfig,
    LoginAuditLog,
)
from dcs_api.models.conditions import ConditionTemplate
from dcs_api.models.safeguards import (
    FinancialNote,
    TemporaryHold,
    TransactionLimit,
)
from dcs_api.models.client_portal import (
    ClientPortalSession,
    ClientPortalUser,
)
from dcs_api.models.telephony import (
    Call,
    CallDisposition,
    CallEvent,
    PhoneNumber,
)
from dcs_api.models.printing import (
    Printer,
    PrintJob,
)
from dcs_api.models.scanning import (
    Check,
    ScanJob,
    Scanner,
)

__all__ = [
    # Tenant
    "Tenant", "User", "Role", "Permission", "RolePermission", "UserRole", "AuditLog",
    # Consumer
    "Consumer", "ContactMethod", "Consent", "SuppressionEntry",
    # Account
    "Account", "DebtInstrument", "Case", "Dispute", "Notice",
    "Payment", "PaymentAllocation", "Fee",
    # Litigation
    "LitigationCase", "Judgment", "JudgmentInterestAccrual",
    # Compliance
    "PolicyPack", "RateTable", "RateTableEntry", "StatuteOfLimitationsRule", "UsuryRule",
    # Calculation
    "CalculationRequest", "CalculationResult",
    # Customization
    "ReportTemplate", "ReportExecution", "ImportTemplate", "ImportJob",
    "ExportTemplate", "ExportJob", "Script", "ScriptExecution",
    # Workflow
    "ActivityCode", "ActivityEntry", "WorkflowChain", "WorkflowChainStep",
    "WorkQueue", "QueueEntry",
    # Trust
    "TrustAccount", "TrustTransaction", "BankReconciliation", "ReconciliationItem",
    # Documents
    "DocumentTemplate", "DocumentGeneration", "DocumentBatch",
    # Automation
    "EventRule", "EventLog", "ScheduledJob", "JobExecution",
    # Tags
    "TagDefinition", "TagAssignment",
    # Performance
    "GoalGroup", "CollectorGoal", "PerformanceSnapshot",
    # Credit Reporting
    "BureauConfig", "BureauBatch", "BureauRecord",
    # EDI
    "DataExchangeFormat", "DataExchangePartner", "DataExchangeBatch",
    # Skip Trace
    "SkipTraceRequest", "SkipTraceResult",
    # Masking
    "MaskingPolicy",
    # Waterfall
    "PaymentWaterfall", "WaterfallRule",
    # Costs
    "CostEntry", "CostDisbursement", "CostBilling",
    # Remittance
    "RemittanceStatement", "RemittanceLineItem", "RemittanceConfig",
    # Flash Messages
    "FlashMessageTemplate", "AccountFlashMessage",
    # Reviews
    "ReviewTemplate", "ReviewTemplateItem", "AccountReview", "AccountReviewItem",
    # Courts
    "Court", "CourtCostOverride", "CourtRepresentative",
    # Payment Plans
    "PaymentPlan", "ScheduledPayment",
    # Batch Letters
    "BatchLetterConfig", "BatchLetterRule",
    # SubPlans
    "SubPlan", "SubPlanStep",
    # Audit
    "AccountAccessLog", "AuditConfig", "LoginAuditLog",
    # Conditions
    "ConditionTemplate",
    # Safeguards
    "TransactionLimit", "FinancialNote", "TemporaryHold",
    # Client Portal
    "ClientPortalUser", "ClientPortalSession",
    # Telephony
    "Call", "CallEvent", "CallDisposition", "PhoneNumber",
    # Printing
    "Printer", "PrintJob",
    # Scanning
    "Scanner", "ScanJob", "Check",
]
