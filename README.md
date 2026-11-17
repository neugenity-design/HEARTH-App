# Hearth

Settings includes **Import / Export** with a dedicated TenantCloud ZIP/XLSX/CSV workflow, partial-file previews, duplicate protection, preserved originals, official-template CSV exports, and native Hearth CSV. See [data-transfer behavior and verification](docs/DATA-TRANSFERS.md) for supported sections and source limitations. The verified TenantCloud import is now the main workspace.

Property cards support **Add photo / Change photo**, using an uploaded home image or an image already attached to that property. **Use placeholder** resets the cover without deleting the attachment. Venmo and Cash App are available as recorded payment methods and list filters. Search no longer redraws recursively when its field loses focus.

**H.E.A.R.T.H. — Home Expense And Rental Tracking Hub**

Local property management using the owner's imported records. No subscriptions or third-party runtime dependencies are required. Core records work offline; sending email through Google Workspace requires an internet connection.

## Open it

Double-click **Hearth.pyw** in this folder. Windows may display it simply as **Hearth** when file extensions are hidden. It opens the main workspace at http://127.0.0.1:8768 with the records imported from the owner's TenantCloud export and the separately verified rent-payment attachments.

Double-click **Hearth Tools.pyw** to restore a backup into a separate workspace. Existing data is preserved.

The Python server must be running while you use the app. The launcher starts it in the background. Closing the browser does not delete data. Python 3.11 or later is required (Python 3.14 is installed on this computer).

## What works

- Property and unit records; tenant contacts; vendors.
- Fixed and month-to-month lease records, two-tenant rent splitting, renewal drafts, signed document attachments, printable lease summaries, and a section-based lease editor with saved drafts, preview, HTML generation and browser printing. The detailed California default is pending identification of the full source lease; the short source template is clearly marked temporary.
- Monthly charge generation, partial payments, remaining balances, deposits recorded separately from income, numbered printable receipts, and optional Google Workspace delivery of locked receipts. Recording a payment does not transfer funds.
- Expense entry, paid/unpaid status, dates, categories, receipt files, payees, and links to maintenance jobs.
- Work requests, priorities, status board, estimates, actual costs, vendors, access instructions, files, and completion dates.
- Reports for cash flow, paid expense categories, work categories, individual work costs, rent roll, and current tenant balances.
- Custom fields (text, long text, number, date, choice, yes/no) on every main record, plus editable category lists.
- Local inspection notes, applicants, listing drafts, tasks, documents, search, filters, CSV export/import, audit history, archive/restore, and full backups.
- Shared sortable result tables, shared search and dropdown controls, and clickable KPI cards with record breakdown dialogs. See [shared controls and lease documents](docs/SHARED-UI-AND-LEASES.md).

## Financial behavior

- Amounts are validated to two decimal places and calculations use integer cents.
- Rent charges represent amounts owed; payments represent money received. A payment applied to a charge reduces its balance.
- Payments cannot exceed a linked charge's remaining balance. Unallocated payments can be recorded separately; they do not automatically settle a charge.
- Issued receipts keep a snapshot of the original tenant, property, amount and owner details. To correct a payment, void it and create a replacement. The old receipt is then marked VOID.
- Expense summaries distinguish paid and unpaid costs. Cash-flow reporting uses the payment date; work-cost reporting includes paid and unpaid costs by invoice date. Estimates are never added to actual costs.
- The built-in Security deposit category is excluded from income. Refunds, applying deposits, credits, and a full liability ledger are not implemented yet.
- Rent generation is an explicit action. It generates monthly charges from a lease's start through the selected date, with one generated charge per lease, tenant and month. There is no background scheduler. Changing a rent amount affects newly generated charges; existing charges retain their amount. Void generated charges remain in the generation history.
- A due day beyond a month's length uses that month's final day. Mid-month starts are not automatically prorated. Enter any prorated opening charge separately. Late-fee terms are recorded but late fees are charged manually.
- Category names are saved on transactions. Renaming a category does not rewrite historical records.
- Imported rows are validated in one transaction. An invalid row rolls back the whole import. Native CSV imports create new records. The dedicated TenantCloud workflow separately protects against repeated source records.

## Back up and restore

Use **Settings → Download full backup**. The ZIP contains the SQLite database, uploaded files, and a format manifest. Keep a copy off this computer.

Restore from **Hearth Tools.pyw → Restore a backup**. It restores into a new timestamped folder and verifies database integrity and file checksums. It never replaces your original workspace. A restored workspace opens on port 8767. Close any previously running restored workspace before opening a different restored backup on that port.

## Google Workspace email

Settings includes **Google Workspace email**. Enable the Gmail API in a Google Cloud project, configure the OAuth audience as Internal, create a Desktop app OAuth client, and download its JSON file. Add that file in Hearth, then select **Connect** and sign in to the sender mailbox. Hearth requests only identity and Gmail send access. It never stores the Google account password. On Windows, the OAuth client and refresh token are protected with Windows Data Protection and excluded from Hearth backups.

When a payment has a locked receipt and its tenant has an email address, **Payment actions → Send receipt to tenant@email** shows the exact recipient and asks for confirmation before sending. The email includes the locked receipt as a PDF attachment and records the delivery action in Hearth's audit history.

## Review coverage and current limits

This is a working local first version, **not a claim of complete feature parity or an exhaustive button-by-button audit**. The review log is in `docs/WORKFLOW-REVIEW.md` and the feature map is in `docs/FEATURE-MAP.md`.

Source business records were not edited. The verified TenantCloud export and 44 rent receipt attachments populate the main workspace. A downloaded source lease is kept in ignored private validation storage, outside public app files. Its reusable template excludes original personal and signing information.

Not connected: tenant/service-provider portals, general messaging threads, online rent collection, bank feeds/reconciliation, credit/background screening, e-signatures, external listing syndication, legally reviewed document catalogs, background automations, tax forms, and online multi-user hosting. Google Workspace can send locked payment receipts after OAuth setup. Inspections are locally recorded findings rather than tenant-submitted inspection requests. Listing and application records are private management entries.

## GitHub and Replit

The repository includes Replit import configuration and password protection for nonlocal runs. See [Replit preparation](docs/REPLIT.md). Personal databases, receipt uploads, backups, private validation evidence, and Google credentials are excluded from Git.

The browser UI uses a server API; the database and files are already separate from the browser. A production Replit deployment still needs its SQLite records migrated to Replit Database and uploaded documents migrated to Replit App Storage. Local mode continues to bind only to this computer and reject foreign browser origins.

## For development

Run `python server.py` for the main workspace. Run `python -m unittest discover -s tests -v` for domain and HTTP checks and `node tests/test_ui_helpers.mjs` for shared controls and document checks.

Data lives in `data/hearth.sqlite3` and `data/uploads/`. Both are excluded from source control. The app uses only Python standard-library modules, plain JavaScript, and local CSS/SVG assets.
