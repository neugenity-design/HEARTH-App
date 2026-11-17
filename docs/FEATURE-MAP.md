# Hearth feature map

The interactive viewer is a functional local first version. It does not imply full commercial-product parity.

| Area | Working in local app | Remaining for fuller parity |
|---|---|---|
| Properties | Create/edit, single and multi-unit metadata, units, amenities, utilities notes, files, cover-photo upload/replacement, related history | Photo gallery controls, structured utility-provider assignments, occupancy board |
| Tenants | Contacts, insurance details, emergency contacts, pets, vehicles, documents, balances and leases | Tenant login, invitations, separate structured dependent/pet/vehicle tables |
| Leases | Fixed/month-to-month, two-party rent shares, terms, recurring monthly charge generation, renewal draft, printable summary, signed-file storage, section-based draft editor, preview and generated HTML/printing | Full multi-step move-in/out, unlimited tenant splits, proration, automatic late fees, full California source template pending, e-signatures |
| Rent & receipts | Charges, partial payments, charge allocation, outstanding balances, immutable numbered receipts, print/PDF, void history | Actual online collection, recurring scheduler, credit application, refunds, full deposit return/application ledger |
| Expenses | Paid/unpaid entry, categorization, payee/vendor, files, work links, search/filter, export/import | Expense partial payments, recurring expense schedules, bank reconciliation |
| Maintenance | Create/edit jobs, priority, status list/board, assignee, access notes, estimates, actual categorized expenses, custom fields and attachments | Tenant/provider communication, automatic assignment, recurring schedules, structured sub-issues |
| Reports | Cash flow, expenses by category/property, work actual/estimated costs, rent roll, current balances, print/PDF, CSV | Full tax reports, aging buckets, configurable columns/grouping, accrual accounting, bank reconciliation |
| Files | Durable upload, record association, open/download, backup | OCR, full file search/grouping, thumbnail gallery, trash and relinking |
| Inspections | Local condition records, room notes, attachments and follow-up | Tenant-submitted checklists, request expiration, inspection templates/sign-off |
| Applicants & listings | Local applicant records/status, draft listing copy, property links | Public forms, syndication, screening, automated decisions, outbound notices |
| Customization | Typed custom fields on all main records, required validation, custom categories | Formula fields, field-level permissions, custom report layouts |
| Data | SQLite, disk files, audit log, optimistic revisions, atomic CSV imports, full verified backup/restore, soft archive | Automatic off-device backups, hosted authentication, multi-user access |

## Online transition

Keep the existing browser/API separation and migrate the domain operations into an authenticated production service. Add owner and tenant roles, secure uploaded-file access, reliable scheduled jobs, managed database/storage backups, and the external integrations actually wanted. No subscriptions or pricing tiers are present in the app itself.

Result tables, search fields and dropdowns share base implementations. All KPI cards open scoped record dialogs using the shared sortable table.
