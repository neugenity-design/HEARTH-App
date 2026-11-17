# Property management workflow review

Review date: 2026-09-30. Method: read-only inspection of the user's signed-in reference account. No source code, branding, or paid document templates copied. No records submitted or modified.

This is a live coverage log, not a claim of exhaustive feature parity. "Observed" means the rendered page or dialog was inspected. A workflow that requires saving, purchasing, sending invitations, signing documents, bank connection, or deleting real data cannot be safely completed during read-only review.

## Observed

- Navigation: dashboard; portfolio; listings and applications; renters; transactions; revenues; expenses; reconciliation; reports; documents; maintenance; inspections; messaging; search; notifications; settings.
- Portfolio list: property and unit tabs, search, status/occupancy/type/balance filters, additional filters, import, add property, property accounting, tenants, maintenance links.
- New property form: name, year built, MLS, full address, country, single or multi unit type, beds, baths, area, market rent, deposit, parking/laundry/air conditioning, standard and custom features/amenities, photo gallery, documents.
- Property detail: summary, utilities, files, edit, list, move in, actions, occupancy, tenant links, banking/team assignments, accounting summary.
- Utilities: maintenance assignee, responsibility, providers. Responsibility dialog selects utility and payer and applies a default to leases.
- Lease list: grouped by property, active/ended/past states, start/end dates or month-to-month, tenants, rent/schedule/currency, row actions. Tabs for leases, occupancy board, balances, renters. Search, date/property/tenant/status filters, import, move in.
- Lease setup opening: property/unit, fixed or month-to-month, start/end, lease number, convert to month-to-month. Visible workflow steps: terms, tenants, invoicing type, recurring rent, transactions, payments, utilities/providers, summary. Later steps are not yet verified.

## Scope decisions

- Local first, eventual online use (user confirmed). Persist records in SQLite and attachments on disk behind a server API; do not use browser storage as the database.
- Personal landlord app with no subscription or billing plans. Original app name: Hearth.
- Core priorities: properties and units, tenants, leases, rent charges/payments and printable receipts, expense receipt uploads, work orders and categorized actual costs, custom fields, reports and backups.
- Paid external services such as payment processing, credit screening, insurance, and legally reviewed document catalogs require separate integrations; do not represent them as implemented by local bookkeeping controls.

## Additional observed surfaces

- Existing lease detail: timeline, renewal, actions, tenant list, dependents, recurring transactions, agreements/notices, insurance, utilities. Recurring-rent edit dialog: enabled state, monthly frequency, due day, individual tenant amounts, total; updates affect future invoices. The dialog was closed without saving.
- Expense list: invoices/payments/recurring tabs; all/open/partial/overdue/void states; money-in and money-out menus; date/client/property/category filters; totals; sorting; row selection and actions.
- Money-out menu: record expense, recurring expense, bulk change, return deposit, apply deposit. Only record-expense form was opened.
- Expense form: property/general expense, category/subcategory tree, due date, amount, mark-paid toggle, payer/payee, tags, details, upload file, create/cancel. Category picker includes acquisition, appliances, travel, capital improvements, cleaning, and nested categories. No expense was saved to the reference account.
- Maintenance list: requests, board, recurring, service professionals; status/property/assignee/client filters; add request; settings. New-request workflow: property/unit, priority, due date, photos/video, four-level issue category, title, rich-text description; later steps named tenants/access and assignee. Those later steps were not submitted.
- Report catalog: contact, lease, tenant, provider, rent-roll, maintenance, insurance, screening, vacancy, deposits/liabilities, general income/expenses, property income/expenses, payment and tax reports. Operating statement and tax preparation are upgrade-gated. Property-expense report: date/property/category filters, cash accounting basis, grouping, columns and download.
- Documents: landlord forms, own templates, file manager. Catalog has paid state forms and general forms. Template content was not copied. File manager has property/file-type filters, grouping, list/grid and bulk controls, name/type/size/date, file preview and row menus. No private file was migrated.
- Inspections list: status/type filters, views and request-inspection action. Request dialog: property, move-in/move-out, required sections, expiration date/time, request/cancel. No request sent.
- Listings list: listings/leads/applications/screenings tabs, status/days-listed/syndication filters, add/list-unit, own website. Listing wizard stages: property, amenities, media, description, lease details, pets, screening, contact, ribbon, syndication. Only the opening property selection was inspected; no listing was published.
- Settings directory: account profile/security/integrations/notifications, subscription, invoice rules/late fees/tags, payments, application fees/form/terms, website domain/style, team roles/property permissions, maintenance requests/automation, reports layout.
- Accounting settings: recurring invoice early-posting days, one-time and daily late fees, owner visibility, grace period/time. Tags page: search and add tag.
- Maintenance settings: recurring-service advance days, tenant/provider contact visibility, automatic message-channel creation; automation has assignee and provider-resolution review rules. Automatic assignee is upgrade-gated.
- Reconciliation page: paid upgrade gate; bank-feed connection disabled. No bank account connected.
- Tenant detail: outstanding balance, deposits, credits, roommate links, statement and notice actions, invoice creation, timeline, profile/leases/transactions/insurance/applications/requests tabs. Profile has names/company/DOB, multiple contact details, forwarding address, emergency contacts, pets, vehicles, attachments.

## Still unverified

Update 2026-09-30: the user explicitly authorized exporting account data and testing migration. Generated and downloaded the all-time account export in Settings → Security, and downloaded the official property, tenant, and lease import templates. No source business records were changed or imported back. See DATA-TRANSFERS.md for the real-file mapping, partial-file behavior, validation results and remaining source-format limitations.

The requested exhaustive review is **not complete**. Remaining items include every row-action menu and nested filter, full creation and amendment wizard steps, tenant creation/editor, applications/leads/screening subflows, agreement/template editor and signing flows, rent receipt print/download variants, deposit return/application/credits/refunds, recurring expense and maintenance configuration, all report configurations, user permissions, notifications, messaging, and integrations.

Flow completion that saves or modifies source records, sends messages/invitations, requests inspections, publishes listings, connects banks, purchases upgrades, or signs agreements was intentionally not performed. Upgrade-gated content could not be inspected from this plan. No completion or parity claim is made for these surfaces.

## Local viewer verification

- Browser-created a fictional property and a custom choice field.
- Browser-created a work order with that field, then linked a paid expense.
- Browser-uploaded a sample receipt after the browser extension's file-access option was enabled; verified the attached file in the expense record.
- Browser-recorded a partial rent payment and verified the generated numbered printable receipt.
- Automated domain and HTTP checks cover money precision, partial/overpayments, immutable receipts, voiding, deposit income exclusion, monthly generation and changing due dates, split rent, category cost totals, custom validation, relation integrity, revision conflicts, backup/restore integrity, upload/download, import rollback, and origin/token checks.

## Lease document follow-up — September 30, 2026

The source agreement that was available contained 15 clauses plus executed signatures and a signature certificate. Its clauses were transcribed into a temporary template without personal or signer information. The intended complete owner-approved lease has not yet been identified. No paid state form was purchased or copied.

Shared controls and all 24 KPI dialog paths were checked in the sample browser. Lease section ordering, preview, save/reload, and generated attachment were exercised using fictional sample data. Shared helper tests and 35 backend tests passed. Browser PDF printing has not yet been verified.

The two current co-tenants' message threads were also checked; both show only the initial welcome screen with no messages or attachments. No messages were sent.
