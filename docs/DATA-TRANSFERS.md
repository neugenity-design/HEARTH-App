# Import and export

Settings → Import / Export is the entry point. TenantCloud is the first supported application; Hearth/custom CSV remains available separately. No other vendor is advertised as compatible.

## TenantCloud to Hearth

In TenantCloud, open Settings → Account settings → Security → Export data. Choose All time and the desired sections. Download the generated ZIP from Downloads. Hearth accepts that ZIP or multiple individual XLSX/UTF-8 CSV files with their original column headings. Limits: 20 MB combined uploads, 100 MB expanded archive contents, 5,000 archive entries, 10,000 rows per worksheet.

Hearth recognizes exact verified column layouts, not filenames. A file from another system with different headings is rejected with a format error. A deliberately identical schema cannot prove which application produced a file; this is format validation, not authentication.

The preview lists included/missing sections, destinations, new/matched/duplicate records, and rows needing review. Missing files do not block independent records. Rows lacking required relationships are reported and can be retried after importing the dependencies. Unexpected failures roll back the batch. Valid rows and originals are saved only after the user selects Import available data.

Mappings verified against the actual account export on 2026-09-30:

- Property/unit summary and detail workbooks → Properties and Units. Extra source attributes remain viewable on the record.
- Tenant summary and personal-information workbooks → Tenants, retaining original structured fields.
- Lease summary and individual lease/Residents worksheets → Leases linked to properties and tenants.
- Income transactions → Charges plus settlement summaries for paid portions. Existing invoice balances are preserved. Imported summaries do not issue new receipts.
- Expense transactions → Expenses. A partial expense creates paid and unpaid portions so cash expense is not overstated.
- Credits and unsupported accounting types → Source history, excluded from cash totals pending reconciliation.

All input files are retained byte-for-byte in import history and included in full backups. Unsupported workbooks and attachments remain in the original archive; their original bytes are retained, but they are not claimed to be mapped into native sections. Maintenance, applications, owners, service professionals, tasks, and message schemas were absent from the supplied archive and therefore are not yet verified adapters. The preview identifies unrecognized layouts.

Attachment verification, September 30, 2026: the actual all-time account ZIP contains 18 XLSX files and no receipt images or PDF attachments. The income and expense workbooks contain no embedded media, external-file links, or worksheet hyperlinks; their columns contain no attachment reference. The signed-in Export data dialog has no separate attachment/files option. Uploaded payment screenshots remain visible in the source File manager but are not present in this archive. Importing this ZIP therefore does not migrate payment evidence. A separate attachment migration must capture each source transaction ID and its associated files before linking them to Hearth records; filenames, dates, or matching amounts alone are not sufficient proof of a relationship. A verified one-time rent-receipt migration was subsequently completed as described below; automatic attachment association from arbitrary exports is still unsupported.

Exact repeats are skipped. Changed versions of previously imported records are flagged rather than overwriting edits. Exact unique property/address and tenant/email matches can reuse existing records. Ambiguous matches are reported.

## Important source limitations

The account export combines installments into transaction totals and provides only its Date paid field. Historical cash timing and any credit allocation cannot be reconstructed perfectly from those summaries. Reports display an imported-summary notice. Credits remain separately visible rather than being counted twice as income.

The lease export does not include individual rent shares or complete deposit terms. Imported leases retain all source fields but have automatic rent generation turned off for review. A two-person lease is linked to both tenants; unknown shares are clearly flagged. Larger-party leases are retained for review rather than silently dropping residents.

## Hearth to TenantCloud

Select Export data → TenantCloud → section. Property, tenant, and lease exports use the exact official import-template columns downloaded from the signed-in application on 2026-09-30. Downloads split into 500-row CSV files when necessary. Required missing fields are reported before download. No files are uploaded into the real TenantCloud account, no invitations are sent, and no invoices are created there.

Lease export allows active leases or all leases. Ended leases with missing end dates are blocked from export to prevent recreating them as active. TenantCloud has no status column in the template. Disabled recurring rent is exported without automated rent invoices and disclosed in the preview; deposit invoicing is omitted where allocation/date are unknown. The template cannot carry historical balances, attachments, custom fields, lease numbers, or every note. Native Hearth CSV and full backups preserve the broader Hearth data.

The optional transaction source archive uses TenantCloud's transaction export columns for reference. It is **not an upload-ready transaction import**: no corresponding self-service importer has been verified. Original imported transaction snapshots are retained as such in this archive.

## Verification

- Browser-exported the real account ZIP; browser-selected TenantCloud in Hearth and imported the ZIP into the separate workspace at port 8770 (`migration-test-data`). Personal workspace at port 8768 remains empty; sample workspace at 8766 remains separate.
- Imported 2 properties, 5 tenants, 6 leases, 33 expenses, 130 rent charges, and 109 settlement summaries. Preserved 6 credit records. No mapped-row errors.
- Original total unpaid charges: $19,950, including future charges. Past/current charges: $17,100, matching the visible property balances. Paid expenses: $698.14. Rent settlement summaries: $90,850. Credit source records: $449.99, separately retained.
- Re-previewing the same archive identifies all 182 source records as duplicates, creating none.
- HTTP test rejects a CSV with another system's schema.
- Generated property, tenant and active-lease CSV headers match the three downloaded official templates; row lengths and representative values verified. Reverse import was not submitted to the source account.
- 35 automated checks pass, including existing bookkeeping checks, independent partial imports, dependency retries, duplicate/change protection, malformed input, archive traversal, rollback on injected failure, preservation of originals, export limits, and lease-date constraints.

## Adding another application

Capture representative real export files and official import templates. Add a named, versioned adapter with exact signatures, explicit field/relationship mappings, missing-data notices, loss reporting, fixtures, and round-trip tests. Do not route other vendors through TenantCloud's mapper or claim support from a filename alone. `transfers.py` contains the current parser, planning/commit workflow and exporter; the API/UI source selector must advertise only verified adapters.

## Official references

- [Export account data](https://support.tenantcloud.com/en/articles/11898086-how-do-i-export-my-account-data)
- [Import properties](https://support.tenantcloud.com/en/articles/11933866-how-do-i-import-the-property-data)
- [Import leases](https://support.tenantcloud.com/en/articles/12820238-how-do-i-import-leases)

The live account and downloaded workbooks were the source of the implemented schemas. Articles describe the surrounding workflow.

The browser download test saved `TenantCloud_properties.csv` successfully through Hearth’s file-saving control without navigating away from the app.

## Verified rent receipt migration — September 30, 2026

At the owner's request, inspected all four pages of the source transaction list and downloaded the original attachments from all 44 rent transactions showing attachments. Each file was mapped using its actual transaction detail page and the existing `transfer_sources` transaction ID mapping, then attached to the corresponding imported payment in `migration-test-data` (port 8770). No filename/amount matching was used to infer transaction relationships.

Imported 44 originals totaling 9,495,169 bytes. Verified every stored file and all 44 served attachment URLs against SHA-256 hashes. Properties, tenants, leases, charges, payments, expenses, issued receipts and financial reports were unchanged. A pre-import backup and private verification manifest are kept under ignored `private-validation/payment-receipts/`. Import history contains a downloadable archive of all 44 originals and verified transaction relationships, included in full backups. Personal and fictional sample workspaces were not modified.

This operation covers rent payment attachments. Subscription-expense documents and the separate credit-transaction attachment were outside this rent-receipt batch.
