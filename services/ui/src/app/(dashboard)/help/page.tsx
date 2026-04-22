'use client';

import { useState } from 'react';
import { PageHeader } from '@/components/shared/page-header';
import {
  BookOpen,
  Code,
  BarChart3,
  Upload,
  Download,
  Zap,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Sparkles,
  Send,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';

type Tab = 'scripting' | 'reports' | 'imports' | 'exports' | 'automation' | 'assistant';

const TABS: { id: Tab; label: string; icon: typeof Code }[] = [
  { id: 'scripting', label: 'Scripting', icon: Code },
  { id: 'reports', label: 'Reports', icon: BarChart3 },
  { id: 'imports', label: 'Imports', icon: Upload },
  { id: 'exports', label: 'Exports', icon: Download },
  { id: 'automation', label: 'Automation', icon: Zap },
  { id: 'assistant', label: 'AI Assistant', icon: Sparkles },
];

function CodeBlock({ code, title }: { code: string; title?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative group rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-700 my-4">
      {title && (
        <div className="bg-neutral-100 dark:bg-neutral-700 px-4 py-2 text-xs font-semibold text-neutral-600 dark:text-neutral-300 flex items-center justify-between">
          <span>{title}</span>
          <button onClick={handleCopy} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200">
            {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
      )}
      <pre className="p-4 bg-neutral-900 text-green-400 text-sm font-mono overflow-x-auto whitespace-pre-wrap">{code}</pre>
    </div>
  );
}

function Section({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-neutral-200 dark:border-neutral-700">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between py-4 text-left hover:text-primary-600">
        <span className="text-base font-semibold text-neutral-800 dark:text-neutral-200">{title}</span>
        {open ? <ChevronDown className="h-5 w-5 text-neutral-400" /> : <ChevronRight className="h-5 w-5 text-neutral-400" />}
      </button>
      {open && <div className="pb-6 text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">{children}</div>}
    </div>
  );
}

function RefTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto my-4 border rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 dark:bg-neutral-700">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-4 py-2 text-left font-medium text-neutral-600 dark:text-neutral-300">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-200 dark:divide-neutral-700">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className={cn('px-4 py-2', j === 0 && 'font-mono text-primary-600 dark:text-primary-400')}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScriptingHelp() {
  return (
    <div className="space-y-0">
      <Section title="Overview" defaultOpen>
        <p>
          DCS Script is a safe, sandboxed domain-specific language for custom business logic.
          Scripts run in a restricted environment with no file I/O, no network access, no imports,
          and no access to Python internals. They operate on your tenant&apos;s data through a
          controlled context.
        </p>
        <p className="mt-3">Use scripts for:</p>
        <ul className="list-disc pl-6 mt-2 space-y-1">
          <li>Flagging accounts approaching statute of limitations</li>
          <li>Custom compliance checks per jurisdiction</li>
          <li>Automated account status transitions</li>
          <li>Report post-processing and transformations</li>
          <li>Import/export data validation hooks</li>
          <li>Scheduled automation tasks</li>
        </ul>
      </Section>

      <Section title="Language Reference">
        <h4 className="font-semibold mb-2">Statements</h4>
        <RefTable
          headers={['Statement', 'Syntax', 'Description']}
          rows={[
            ['PARAM', 'PARAM name TYPE default', 'Declare a parameter with type and default value'],
            ['SET', 'SET variable = expression', 'Assign a value to a variable'],
            ['QUERY', 'QUERY entity WHERE conditions', 'Query data with optional filters joined by AND'],
            ['FOR EACH', 'FOR EACH item IN collection: ... END', 'Iterate over a list of items'],
            ['IF / ELIF / ELSE', 'IF condition: ... ELIF condition: ... ELSE: ... END', 'Conditional execution'],
            ['FLAG', 'FLAG entity AS "label" WITH key = value', 'Flag an entity with metadata'],
            ['LOG', 'LOG "message with $variables"', 'Log a message (visible in execution output)'],
            ['RETURN', 'RETURN expression', 'Return a result and end execution'],
          ]}
        />

        <h4 className="font-semibold mt-6 mb-2">Data Types</h4>
        <RefTable
          headers={['Type', 'Examples', 'Notes']}
          rows={[
            ['STRING', '"hello", \'world\'', 'Quoted text'],
            ['INTEGER', '42, -10, 0', 'Whole numbers'],
            ['DECIMAL', '3.14, 0.05', 'Floating point numbers'],
            ['BOOLEAN', 'TRUE, FALSE', 'Case-insensitive'],
            ['LIST', '["active", "pending"]', 'Comma-separated in brackets'],
            ['NULL', 'NULL, NONE', 'Null/empty value'],
          ]}
        />

        <h4 className="font-semibold mt-6 mb-2">Operators</h4>
        <RefTable
          headers={['Category', 'Operators']}
          rows={[
            ['Comparison', '==  !=  >  >=  <  <=  IN  NOT_IN  LIKE'],
            ['Arithmetic', '+  -  *  /  %'],
            ['Logical', 'AND (in WHERE/IF conditions)'],
            ['Access', '. (dot notation for object fields, e.g. account.status)'],
            ['Variable', '$ (prefix for variable references, e.g. $jurisdiction)'],
          ]}
        />
      </Section>

      <Section title="Built-in Functions">
        <RefTable
          headers={['Function', 'Parameters', 'Returns', 'Description']}
          rows={[
            ['days_since(date)', 'date or date string', 'integer', 'Days between the given date and today'],
            ['days_until(date)', 'date or date string', 'integer', 'Days between today and the given date'],
            ['sol_years(jurisdiction)', 'state code (e.g. "NJ")', 'integer', 'Statute of limitations years for a jurisdiction'],
            ['abs(number)', 'number', 'number', 'Absolute value'],
            ['round(number, places)', 'number, precision', 'number', 'Round to N decimal places (default 2)'],
            ['upper(string)', 'string', 'string', 'Convert to uppercase'],
            ['lower(string)', 'string', 'string', 'Convert to lowercase'],
            ['len(collection)', 'list or string', 'integer', 'Length of a collection or string'],
            ['now()', '—', 'datetime', 'Current UTC date and time'],
            ['today()', '—', 'date', 'Current UTC date'],
            ['format_currency(cents)', 'integer (cents)', 'string', 'Format cents as "$1,234.56"'],
            ['min(a, b)', 'two numbers', 'number', 'Minimum of two values'],
            ['max(a, b)', 'two numbers', 'number', 'Maximum of two values'],
            ['str(value)', 'any', 'string', 'Convert to string'],
            ['int(value)', 'string or number', 'integer', 'Convert to integer'],
            ['float(value)', 'string or number', 'decimal', 'Convert to float'],
          ]}
        />

        <h4 className="font-semibold mt-6 mb-2">SOL Years by Jurisdiction</h4>
        <RefTable
          headers={['State', 'Years']}
          rows={[
            ['NJ, NY, OH, GA, MA, CT', '6'],
            ['FL, IL, VA', '5'],
            ['PA, CA, TX', '4'],
            ['NC, SC, DE, DC, MD', '3'],
          ]}
        />
      </Section>

      <Section title="Queryable Entities">
        <p>Use these entity names with the QUERY statement:</p>
        <RefTable
          headers={['Entity', 'Key Fields']}
          rows={[
            ['accounts', 'id, account_reference, status, jurisdiction, total_balance, current_principal, current_interest, current_fees, original_creditor, debt_type, date_placed, legal_hold'],
            ['consumers', 'id, first_name, last_name, ssn_last_four, date_of_birth, external_id'],
            ['payments', 'id, account_id, amount, method, status, received_at, source'],
            ['disputes', 'id, account_id, reason, status, filed_at, response_due_date'],
            ['judgments', 'id, judgment_amount, post_judgment_rate, judgment_date, satisfaction_recorded'],
            ['litigation', 'id, account_id, court_name, docket_number, status, filed_date, principal_claimed'],
            ['audit_logs', 'id, action, entity_type, description, user_id, created_at'],
            ['users', 'id, email, first_name, last_name, is_active, is_owner'],
          ]}
        />
      </Section>

      <Section title="Script Types & Triggers">
        <RefTable
          headers={['Script Type', 'Use Case']}
          rows={[
            ['validation', 'Validate data before import or on field change'],
            ['workflow', 'Execute business logic as part of a workflow step'],
            ['calculation', 'Custom calculations (interest, fees, allocations)'],
            ['trigger', 'Run when specific events occur (payment received, status change)'],
            ['report_transform', 'Post-process report data before output'],
            ['import_transform', 'Transform imported data before saving'],
            ['export_transform', 'Transform data before export'],
            ['compliance_check', 'Jurisdiction-specific compliance validation'],
          ]}
        />
        <h4 className="font-semibold mt-6 mb-2">Trigger Events</h4>
        <RefTable
          headers={['Event', 'When It Fires']}
          rows={[
            ['on_payment', 'After a payment is recorded'],
            ['on_dispute', 'When a dispute is filed or status changes'],
            ['on_status_change', 'When an account status changes'],
            ['on_contact', 'When a contact attempt is logged'],
            ['on_import', 'After an import job completes'],
            ['on_export', 'Before an export job runs'],
            ['scheduled', 'On a defined schedule (set in the script config)'],
            ['manual', 'Only runs when triggered by a user'],
          ]}
        />
      </Section>

      <Section title="Examples">
        <h4 className="font-semibold mb-2">1. Flag SOL-approaching accounts</h4>
        <CodeBlock title="sol_warning.dcs" code={`PARAM jurisdiction STRING "NJ"
PARAM warning_days INTEGER 90

QUERY accounts
  WHERE jurisdiction = $jurisdiction
  AND status IN ["active", "payment_plan"]

FOR EACH account IN results:
  SET sol_limit = sol_years($jurisdiction) * 365
  SET days_open = days_since(account.date_placed)
  SET remaining = sol_limit - days_open

  IF remaining < 30:
    FLAG account AS "sol_critical" WITH days_left = remaining
    LOG "CRITICAL: Account $account.account_reference has $remaining days to SOL"
  ELIF remaining < $warning_days:
    FLAG account AS "sol_warning" WITH days_left = remaining
  END
END

RETURN results`} />

        <h4 className="font-semibold mb-2">2. Calculate high-balance summary</h4>
        <CodeBlock title="high_balance_report.dcs" code={`PARAM threshold INTEGER 500000

QUERY accounts
  WHERE total_balance > $threshold
  AND status IN ["active", "payment_plan", "legal"]

SET total = 0
SET count = 0

FOR EACH acct IN results:
  SET total = total + acct.total_balance
  SET count = count + 1
END

SET average = round(total / max(count, 1), 2)
LOG "Found $count accounts over $threshold cents"
LOG "Total balance: " + format_currency(total)
LOG "Average balance: " + format_currency(average)

RETURN results`} />

        <h4 className="font-semibold mb-2">3. Compliance check for contact restrictions</h4>
        <CodeBlock title="contact_compliance.dcs" code={`PARAM jurisdiction STRING "NJ"

QUERY accounts
  WHERE jurisdiction = $jurisdiction
  AND status != "closed"

SET violations = []

FOR EACH account IN results:
  IF account.legal_hold == TRUE:
    FLAG account AS "no_contact" WITH reason = "legal_hold"
    LOG "Account $account.account_reference is under legal hold - no contact allowed"
  END

  SET days = days_since(account.date_placed)
  IF days < 30:
    FLAG account AS "validation_period" WITH days_since_placement = days
  END
END

RETURN results`} />
      </Section>

      <Section title="Safety & Limits">
        <ul className="list-disc pl-6 space-y-2">
          <li><strong>Max 10,000 iterations</strong> — prevents infinite loops in FOR EACH blocks</li>
          <li><strong>Max 50,000 result rows</strong> — prevents memory exhaustion</li>
          <li><strong>No file I/O</strong> — open(), os.*, sys.* are blocked</li>
          <li><strong>No imports</strong> — import statements are blocked</li>
          <li><strong>No code execution</strong> — exec(), eval(), compile() are blocked</li>
          <li><strong>No reflection</strong> — getattr(), setattr(), globals(), locals() are blocked</li>
          <li><strong>No dunder access</strong> — __name__, __class__, etc. are blocked</li>
          <li><strong>Tenant isolation</strong> — scripts can only access data within their own tenant</li>
        </ul>
      </Section>
    </div>
  );
}

function ReportsHelp() {
  return (
    <div className="space-y-0">
      <Section title="Creating Reports" defaultOpen>
        <p>
          The report builder lets you create custom reports that query any entity in the system.
          Reports support filtering, grouping, aggregation, sorting, and multi-format output.
        </p>
        <h4 className="font-semibold mt-4 mb-2">Report Types</h4>
        <RefTable
          headers={['Type', 'Description', 'Best For']}
          rows={[
            ['Tabular', 'Row-by-row listing of records', 'Account listings, payment details, audit trails'],
            ['Summary', 'Grouped data with aggregations', 'Client summaries, aging reports, status distribution'],
            ['Matrix', 'Cross-tabulation (two grouping dimensions)', 'Payment method × status, jurisdiction × debt type'],
            ['Chart', 'Data formatted for visualization', 'Dashboard widgets, trend analysis'],
          ]}
        />
      </Section>

      <Section title="Source Entities">
        <RefTable
          headers={['Entity', 'Available Fields', 'Common Reports']}
          rows={[
            ['accounts', 'account_reference, original_creditor, status, jurisdiction, debt_type, total_balance, current_principal, current_interest, current_fees, original_principal, date_placed, legal_hold', 'Aging, placement, client summary'],
            ['consumers', 'first_name, last_name, ssn_last_four, date_of_birth, external_id', 'Consumer directory, demographics'],
            ['payments', 'amount, method, status, received_at, source, account_id', 'Collections summary, EOD totals, allocation detail'],
            ['disputes', 'reason, status, filed_at, response_due_date, account_id', 'Overdue responses, dispute tracking'],
            ['judgments', 'judgment_amount, post_judgment_rate, judgment_date, satisfaction_recorded', 'Judgment inventory, interest accruals'],
            ['litigation', 'court_name, docket_number, status, filed_date, principal_claimed', 'Case inventory, court activity'],
            ['audit_logs', 'action, entity_type, description, user_id, created_at', 'Audit trail, compliance review'],
            ['users', 'email, first_name, last_name, is_active, is_owner', 'User directory, collector performance'],
          ]}
        />
      </Section>

      <Section title="Column Definition">
        <p>Columns are defined as JSON arrays. Each column object has:</p>
        <CodeBlock title="Column format" code={`[
  {"field": "account_reference", "label": "Account #"},
  {"field": "original_creditor", "label": "Client"},
  {"field": "total_balance", "label": "Balance", "format": "currency"},
  {"field": "status", "label": "Status"},
  {"field": "consumer.last_name", "label": "Consumer"}
]`} />
        <p className="mt-2">
          Use <strong>dot notation</strong> to pull fields from related entities (e.g., <code className="text-primary-600">consumer.last_name</code> when
          reporting on accounts). Available joins: accounts→consumer, payments→account, disputes→account.
        </p>
      </Section>

      <Section title="Filters">
        <p>Filters restrict which records are included. Defined as JSON:</p>
        <CodeBlock title="Filter format" code={`[
  {"field": "status", "op": "in", "value": ["active", "payment_plan"]},
  {"field": "jurisdiction", "op": "eq", "value": "NJ"},
  {"field": "total_balance", "op": "gte", "value": 10000},
  {"field": "legal_hold", "op": "eq", "value": true},
  {"field": "date_placed", "op": "between", "value": ["2024-01-01", "2024-12-31"]}
]`} />
        <RefTable
          headers={['Operator', 'Description', 'Value Type']}
          rows={[
            ['eq', 'Equals', 'Single value'],
            ['neq', 'Not equals', 'Single value'],
            ['gt / gte', 'Greater than / greater or equal', 'Number or date'],
            ['lt / lte', 'Less than / less or equal', 'Number or date'],
            ['in', 'Value is in list', 'Array of values'],
            ['not_in', 'Value is not in list', 'Array of values'],
            ['like', 'Contains (case-insensitive)', 'String'],
            ['between', 'Between two values (inclusive)', 'Array of [min, max]'],
            ['is_null', 'Field is null', 'true'],
            ['not_null', 'Field is not null', 'true'],
          ]}
        />
      </Section>

      <Section title="Grouping & Aggregation">
        <p>For summary reports, group by one or more fields and apply aggregations:</p>
        <CodeBlock title="Group by + aggregation" code={`Group by: ["status"]

Aggregations:
[
  {"field": "id", "function": "count", "label": "Account Count"},
  {"field": "total_balance", "function": "sum", "label": "Total Balance"},
  {"field": "total_balance", "function": "avg", "label": "Average Balance"}
]`} />
        <RefTable
          headers={['Function', 'Description']}
          rows={[
            ['count', 'Count of records in each group'],
            ['sum', 'Sum of values in each group'],
            ['avg', 'Average of values in each group'],
            ['min', 'Minimum value in each group'],
            ['max', 'Maximum value in each group'],
          ]}
        />
      </Section>

      <Section title="Runtime Parameters">
        <p>Reports can accept parameters at execution time, useful for date ranges or jurisdiction:</p>
        <CodeBlock title="Parameter definition" code={`Parameters:
[
  {"name": "start_date", "type": "date", "required": true},
  {"name": "end_date", "type": "date", "required": true},
  {"name": "jurisdiction", "type": "string", "required": false}
]

In filters, reference as:
{"field": "date_placed", "op": "gte", "value": "$start_date"}
{"field": "date_placed", "op": "lte", "value": "$end_date"}`} />
      </Section>

      <Section title="Output Formats">
        <RefTable
          headers={['Format', 'Description', 'Use Case']}
          rows={[
            ['CSV', 'Comma-separated values', 'Excel import, data exchange, bulk review'],
            ['XLSX', 'Excel spreadsheet', 'Client reporting, formatted output'],
            ['JSON', 'JavaScript Object Notation', 'API consumption, integrations'],
            ['PDF', 'Formatted document (structured data)', 'Official reports, legal filings'],
          ]}
        />
      </Section>

      <Section title="Pre-built Report Templates">
        <p>The system includes 17 standard reports across 6 categories. These are read-only system templates — clone them to customize:</p>
        <RefTable
          headers={['Category', 'Report Name']}
          rows={[
            ['Client', 'Client Referral Summary'],
            ['Client', 'Placement Analysis by State'],
            ['Client', 'Client Fee Breakdown'],
            ['Financial', 'Collections Summary'],
            ['Financial', 'End of Day Totals'],
            ['Financial', 'Payment Allocation Detail'],
            ['Performance', 'Collector Performance Summary'],
            ['Aging', 'Account Aging by Status'],
            ['Aging', 'Account Aging by Debt Type'],
            ['Compliance', 'Overdue Dispute Responses'],
            ['Compliance', 'Validation Notice Tracking'],
            ['Compliance', 'Legal Hold Inventory'],
            ['Compliance', 'TCPA Consent Status'],
            ['Litigation', 'Litigation Case Inventory'],
            ['Litigation', 'Judgment Inventory'],
            ['Operational', 'Account Status Distribution'],
            ['Operational', 'Audit Trail'],
          ]}
        />
      </Section>
    </div>
  );
}

function ImportsHelp() {
  return (
    <div className="space-y-0">
      <Section title="Import Templates" defaultOpen>
        <p>
          Import templates define how external files (from creditors, vendors, or other systems) are
          mapped into DCS entities. Each creditor can have their own template with custom field mappings.
        </p>
        <RefTable
          headers={['Supported Format', 'Extension']}
          rows={[
            ['CSV', '.csv'],
            ['Excel', '.xlsx'],
            ['JSON', '.json'],
            ['Fixed Width', '.txt, .dat'],
            ['XML', '.xml'],
          ]}
        />
      </Section>

      <Section title="Field Mappings">
        <p>Map source file columns to DCS fields with optional transformations:</p>
        <CodeBlock title="Field mapping format" code={`[
  {"source": "AcctNo", "target": "account_reference", "required": true},
  {"source": "Balance", "target": "current_principal", "transform": "cents"},
  {"source": "SSN", "target": "consumer.ssn_last_four", "transform": "last_four"},
  {"source": "DOB", "target": "consumer.date_of_birth", "transform": "date", "format": "%m/%d/%Y"},
  {"source": "State", "target": "jurisdiction", "transform": "uppercase"}
]`} />
        <RefTable
          headers={['Transform', 'Description']}
          rows={[
            ['cents', 'Multiply dollar amount by 100 to convert to cents'],
            ['last_four', 'Extract last 4 characters (for SSN masking)'],
            ['date', 'Parse date string using the specified format'],
            ['uppercase', 'Convert to uppercase'],
            ['lowercase', 'Convert to lowercase'],
            ['trim', 'Remove leading/trailing whitespace'],
            ['phone', 'Normalize phone number format'],
          ]}
        />
      </Section>

      <Section title="Validation Rules">
        <CodeBlock title="Validation format" code={`[
  {"field": "current_principal", "rule": "positive"},
  {"field": "date_of_service", "rule": "date_format", "format": "%m/%d/%Y"},
  {"field": "jurisdiction", "rule": "one_of", "values": ["NJ", "NY", "PA", "CA"]},
  {"field": "account_reference", "rule": "required"},
  {"field": "ssn_last_four", "rule": "regex", "pattern": "^\\d{4}$"}
]`} />
      </Section>

      <Section title="Deduplication Strategies">
        <RefTable
          headers={['Strategy', 'Behavior']}
          rows={[
            ['skip', 'Skip rows that match existing records (default)'],
            ['update', 'Update existing records with new data'],
            ['error', 'Fail the import if duplicates are found'],
            ['create_new', 'Always create new records regardless of duplicates'],
          ]}
        />
      </Section>
    </div>
  );
}

function ExportsHelp() {
  return (
    <div className="space-y-0">
      <Section title="Export Templates" defaultOpen>
        <p>
          Export templates define outbound data formats for creditor reporting, regulatory filings,
          or integration feeds. Each template specifies columns, filters, format, and delivery options.
        </p>
        <CodeBlock title="Column format" code={`[
  {"field": "account_reference", "header": "ACCT_NO", "width": 20},
  {"field": "consumer.last_name", "header": "LNAME", "width": 30},
  {"field": "total_balance", "header": "BAL", "format": "dollars"},
  {"field": "status", "header": "STATUS", "width": 15}
]`} />
      </Section>
      <Section title="Scheduling & Delivery">
        <p>Exports can be scheduled with a cron expression and delivered via email:</p>
        <RefTable
          headers={['Setting', 'Example', 'Description']}
          rows={[
            ['schedule_cron', '0 6 * * 1', 'Every Monday at 6 AM'],
            ['schedule_cron', '0 0 1 * *', 'First of every month at midnight'],
            ['recipient_email', 'reports@client.com', 'Email address to receive the export file'],
          ]}
        />
      </Section>
    </div>
  );
}

function AutomationHelp() {
  return (
    <div className="space-y-0">
      <Section title="Event Rules" defaultOpen>
        <p>
          Event rules trigger actions when specific data changes occur. Conditions are evaluated
          in real-time as entities are created or updated.
        </p>
        <CodeBlock title="Condition format" code={`{
  "entity_type": "account",
  "event_type": "status_change",
  "conditions": {
    "field": "status",
    "from": "active",
    "to": "legal"
  },
  "actions": [
    {"type": "create_activity", "activity_code": "LEGAL_REVIEW"},
    {"type": "send_notice", "template": "legal_transfer_notice"},
    {"type": "flag_account", "flag": "legal_review_pending"}
  ]
}`} />
      </Section>
      <Section title="Scheduled Jobs">
        <p>
          Scheduled jobs run at defined intervals. Unlike cron, these are managed in the database
          so each tenant controls their own schedules without server configuration.
        </p>
        <RefTable
          headers={['Job Type', 'Description']}
          rows={[
            ['report_generation', 'Run a report template on schedule'],
            ['export_delivery', 'Generate and email an export'],
            ['compliance_check', 'Run compliance scripts for a jurisdiction'],
            ['aging_update', 'Recalculate aging buckets for accounts'],
            ['interest_accrual', 'Accrue post-judgment interest'],
            ['workflow_advance', 'Process workflow chains and advance steps'],
            ['data_cleanup', 'Archive old records or purge expired data'],
          ]}
        />
      </Section>
    </div>
  );
}

interface AiMessage {
  role: 'user' | 'assistant';
  content: string;
}

function AiAssistant() {
  const [messages, setMessages] = useState<AiMessage[]>([
    {
      role: 'assistant',
      content: 'I can help you create DCS scripts, report templates, import/export mappings, and automation rules. Describe what you need in plain English and I\'ll generate the configuration for you.\n\nExamples:\n• "Create a report showing all accounts in NJ with balance over $5,000"\n• "Write a script that flags accounts within 90 days of statute of limitations"\n• "Build an import template for a CSV file with columns AcctNo, Name, Balance, State"\n• "Set up an automation rule to send a notice when a dispute is filed"',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    // AI endpoint placeholder — swap this for your real AI endpoint when ready
    try {
      const res = await apiClient.post<{ response: string }>('/api/v1/ai/assist', {
        prompt: userMessage,
        context: 'dcs_scripting_and_reports',
        history: messages.slice(-10),
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.response }]);
    } catch {
      // Fallback when AI endpoint isn't connected yet
      const fallback = generateLocalResponse(userMessage);
      setMessages((prev) => [...prev, { role: 'assistant', content: fallback }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-16rem)]">
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="h-5 w-5 text-purple-600" />
          <h3 className="font-semibold text-purple-800 dark:text-purple-300">AI Assistant</h3>
          <span className="text-xs bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded-full">Preview</span>
        </div>
        <p className="text-sm text-purple-700 dark:text-purple-400">
          Describe what you need in plain English. The assistant will generate scripts, report
          definitions, and configurations ready to paste into the builder.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((msg, i) => (
          <div key={i} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div className={cn(
              'max-w-[80%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap',
              msg.role === 'user'
                ? 'bg-primary-600 text-white'
                : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 border border-neutral-200 dark:border-neutral-700'
            )}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-neutral-100 dark:bg-neutral-800 rounded-lg px-4 py-3 border border-neutral-200 dark:border-neutral-700">
              <Loader2 className="h-5 w-5 animate-spin text-primary-600" />
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-2 border-t border-neutral-200 dark:border-neutral-700 pt-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Describe what you want to build..."
          className="flex-1 rounded-lg border border-neutral-300 dark:border-neutral-600 px-4 py-2 text-sm bg-white dark:bg-neutral-800 focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-primary-600 px-4 py-2 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function generateLocalResponse(prompt: string): string {
  const lower = prompt.toLowerCase();

  if (lower.includes('report') && (lower.includes('account') || lower.includes('balance'))) {
    return `Here's a report template for that:\n\n\`\`\`json\n{\n  "name": "Custom Account Report",\n  "source_table": "accounts",\n  "output_format": "csv",\n  "columns": [\n    {"field": "account_reference", "label": "Account #"},\n    {"field": "original_creditor", "label": "Client"},\n    {"field": "total_balance", "label": "Balance"},\n    {"field": "status", "label": "Status"},\n    {"field": "jurisdiction", "label": "State"}\n  ],\n  "filters": [\n    {"field": "status", "op": "in", "value": ["active", "payment_plan"]}\n  ]\n}\`\`\`\n\nGo to **Reports → New Report** and paste the columns and filters JSON into the respective fields. Adjust the filter values as needed.`;
  }

  if (lower.includes('script') && (lower.includes('sol') || lower.includes('statute'))) {
    return `Here's a DCS Script for SOL monitoring:\n\n\`\`\`\nPARAM jurisdiction STRING "NJ"\nPARAM warning_days INTEGER 90\n\nQUERY accounts\n  WHERE jurisdiction = $jurisdiction\n  AND status IN ["active", "payment_plan"]\n\nFOR EACH account IN results:\n  SET sol_limit = sol_years($jurisdiction) * 365\n  SET remaining = sol_limit - days_since(account.date_placed)\n\n  IF remaining < 30:\n    FLAG account AS "sol_critical" WITH days_left = remaining\n    LOG "CRITICAL: $account.account_reference - $remaining days"\n  ELIF remaining < $warning_days:\n    FLAG account AS "sol_warning" WITH days_left = remaining\n  END\nEND\n\nRETURN results\n\`\`\`\n\nGo to **Scripting → New Script**, set the type to "compliance_check", paste the code, and click **Validate** before running.`;
  }

  if (lower.includes('import') && (lower.includes('csv') || lower.includes('template') || lower.includes('mapping'))) {
    return `Here's an import template configuration:\n\n\`\`\`json\n{\n  "name": "Client CSV Import",\n  "target_table": "accounts",\n  "file_format": "csv",\n  "field_mappings": [\n    {"source": "AcctNo", "target": "account_reference", "required": true},\n    {"source": "ClientName", "target": "original_creditor", "required": true},\n    {"source": "Balance", "target": "current_principal", "transform": "cents"},\n    {"source": "State", "target": "jurisdiction", "transform": "uppercase"},\n    {"source": "PlacementDate", "target": "date_placed", "transform": "date", "format": "%m/%d/%Y"}\n  ],\n  "dedup_fields": ["account_reference"],\n  "validation_rules": [\n    {"field": "current_principal", "rule": "positive"},\n    {"field": "jurisdiction", "rule": "one_of", "values": ["NJ","NY","PA","CA","TX"]}\n  ]\n}\`\`\`\n\nGo to **Imports → Templates → New Template** and configure each field mapping.`;
  }

  if (lower.includes('automation') || lower.includes('rule') || lower.includes('trigger')) {
    return `Here's an automation rule configuration:\n\n\`\`\`json\n{\n  "name": "Auto-create legal review on status change",\n  "entity_type": "account",\n  "event_type": "status_change",\n  "conditions": {\n    "field": "status",\n    "to": "legal"\n  },\n  "actions": [\n    {"type": "create_activity", "activity_code": "LEGAL_REVIEW"},\n    {"type": "send_notice", "template": "legal_transfer_notice"}\n  ],\n  "is_active": true\n}\`\`\`\n\nGo to **Automation → Event Rules → New Rule** and paste the conditions and actions JSON.`;
  }

  return `I can help you create:\n\n• **Reports** — "Show me all NJ accounts with balance over $5,000"\n• **Scripts** — "Flag accounts near statute of limitations"\n• **Import templates** — "Map a CSV with columns AcctNo, Balance, State"\n• **Export templates** — "Create a monthly client report in CSV"\n• **Automation rules** — "Send a notice when a dispute is filed"\n\nTry describing what you need in more detail, and I'll generate the configuration for you.\n\n_Note: The AI backend integration is in preview. When connected to an AI model, responses will be more precise and context-aware._`;
}

export default function HelpPage() {
  const [activeTab, setActiveTab] = useState<Tab>('scripting');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Help & Documentation"
        subtitle="Reference guides for scripting, reports, imports, exports, and automation"
        actions={
          <a
            href="/scripting"
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Go to Scripting
          </a>
        }
      />

      <div className="border-b border-neutral-200 dark:border-neutral-700">
        <nav className="flex gap-0 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
        {activeTab === 'scripting' && <ScriptingHelp />}
        {activeTab === 'reports' && <ReportsHelp />}
        {activeTab === 'imports' && <ImportsHelp />}
        {activeTab === 'exports' && <ExportsHelp />}
        {activeTab === 'automation' && <AutomationHelp />}
        {activeTab === 'assistant' && <AiAssistant />}
      </div>
    </div>
  );
}
