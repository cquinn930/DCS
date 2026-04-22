## RBAC defaults

### Roles
- Collector: manage assigned cases, contacts, payments, disputes.
- Supervisor: all collector permissions plus assignment, coaching, escalations.
- Legal reviewer: review disputes, litigation actions, notices.
- Admin: manage users, roles, integrations, configurations.
- Owner: full tenant control including retention, lockdown, and billing.
- Master account: cross-tenant administration without data visibility (metadata only).

### Permission matrix (high level)
- View consumer data: collector, supervisor, legal, admin, owner
- Edit consumer data: collector, supervisor, admin, owner
- Create outbound contact: collector, supervisor
- Manage disputes: collector, supervisor, legal
- Approve litigation actions: legal, owner
- Manage integrations: admin, owner
- Configure retention and consent policies: owner only
- Lift breach lockdown: owner only (master override allowed)

### Permission matrix (detailed)
| Capability | Collector | Supervisor | Legal | Admin | Owner | Master |
| --- | --- | --- | --- | --- | --- | --- |
| View assigned accounts | Yes | Yes | Yes | Yes | Yes | No |
| View all tenant accounts | No | Yes | Yes | Yes | Yes | No |
| Edit account contact info | Yes | Yes | No | Yes | Yes | No |
| Edit balances and fees | No | Yes | No | Yes | Yes | No |
| Create outbound contact | Yes | Yes | No | No | Yes | No |
| Override suppression list | No | No | No | No | Owner only | No |
| Manage disputes | Yes | Yes | Yes | No | Yes | No |
| Approve dispute resolutions | No | Yes | Yes | No | Yes | No |
| Create litigation case | No | No | Yes | No | Yes | No |
| Approve litigation filings | No | No | Yes | No | Yes | No |
| Manage users | No | No | No | Yes | Yes | No |
| Create custom roles | No | No | No | Yes | Yes | No |
| Assign owner-only permissions | No | No | No | No | Yes | No |
| Configure integrations | No | No | No | Yes | Yes | No |
| Configure policy packs | No | No | No | No | Yes | No |
| Configure retention | No | No | No | No | Yes | No |
| Lift breach lockdown | No | No | No | No | Yes | Yes |
| View tenant metadata | No | No | No | No | Yes | Yes |
| Access consumer data (master) | No | No | No | No | No | No |

### Custom roles
- Admins can create custom roles but cannot grant owner-only permissions.
- Owner can grant any permission within tenant.
- Master account can manage tenants but cannot access consumer data.
