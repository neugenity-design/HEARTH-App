# Shared controls and lease documents

`results-table.js` is the one interactive table renderer and sorting controller. Main lists, related records, reports, import previews and KPI dialogs all call it. Strings, currency and dates sort by value. Empty values sort last. Sorting remains scoped to the particular table, persists across page redraws during the session, and exposes keyboard-accessible header buttons with `aria-sort`.

`search.js` owns the search field, input debounce and case/accent-insensitive, multiword matching. Page search callbacks filter the relevant records; embedded table searches filter only their table without replacing the focused input. Page search combines with other filters. Embedded tables keep their query and sort independently.

`controls.js` owns HTML escaping, dropdown rendering, option rendering and dynamic option updates. Property filters share `propertyFilter()` and `optionsFor()` with form reference dropdowns. The page supplies labels, attributes, selection and option data.

All 24 KPI cards open a record breakdown in the existing modal. Outstanding shows only nonvoid charges with a positive remaining balance. Income excludes void payments and deposits. Deposits and co-tenant lease participation retain their own scope. Expense/report cards use the same filtered records as their totals. Computed net cash flow and remaining estimates explain the arithmetic and show both contributing record sets.

## Lease builder

Open a lease and choose **Review / build lease**. The ordered section cards follow the SOW builder's editing pattern: editable heading/body, Up/Down, Remove, Include, and Add section. Text, details, rent/charges, and blank signature sections are supported. Preview and printing share one renderer. Save draft stores a document snapshot inside the lease JSON under the same optimistic version protection as normal records. Generating saves the draft, attaches a self-contained HTML snapshot, and requests a browser download. **Print / Save PDF** uses the browser print dialog. Attached signed files remain separate from the editable draft.

Document values start from the lease record; changes to document text never rewrite rent charges or lease accounting terms. New renewals do not copy the prior document snapshot. Unsaved edits prompt before leaving or reloading. Saved drafts stay independent of later template edits.

## Provisional source template — full California lease pending

The provisional `california-owner-v1` template was transcribed from the owner's downloaded Basic Residential Lease Agreement for the active 2026 lease, inspected September 30, 2026. It preserves all 15 clauses across agreement pages 1–2. Page 2's executed signature area and all of page 3's signing certificate were excluded. Original names, property address, signing dates, emails, IP addresses and signature graphics are absent from reusable template code. The original PDF is retained only under ignored `private-validation/lease-source/`.

Names, premises, dates, rent, payment day, fees, deposit, utilities and notice period use editable draft context. The source's unfilled state name becomes California; its missing end-date text is replaced by the recorded fixed end date or month-to-month term. Original selected payment methods and utility allocations initialize editable defaults. No new California legal review or required disclosure validation is claimed.

Hearth implements its own lightweight, section-based document builder without adding a framework runtime dependency.

The initial short agreement is labeled temporary and must not be represented as a completed California default. Preserve every clause and addendum when a complete owner-approved source is added, excluding executed signer details and audit certificates.
