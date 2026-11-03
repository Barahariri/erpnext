# ERPNext v16 — Construction Enterprise Demo

**Status: experimental test-data generator.** It is not a legally accurate tax return, a production-ready accounting implementation or a verified result of a complete site run.

Source: Barahariri/erpnext, branch feature/construction-enterprise-demo.
Compatible source baseline: ERPNext 16.53.0 / Frappe 16.54.0.
The reported Docker installation is ERPNext 16.53.0 and Frappe 16.54.0;
HRMS did NOT appear in the reported installed applications.

## Demonstration plans

| Company | Country | Currency | Staff | Projects | Equipment | Customers | Suppliers |
|---|---|---|---:|---:|---:|---:|---:|
| شركة ركيزة الأفق للمقاولات العامة | Kuwait | KWD | 410 | 34 | 190 | 100 | 140 |
| شركة رواسي الدوحة للإنشاءات | Qatar | QAR | 350 | 28 | 150 | 80 | 120 |
| شركة مدائن الشام للهندسة والمقاولات | Syria | SYP | 320 | 24 | 130 | 70 | 100 |

Period: 2023-11-01 to 2026-10-31. Sample stock materials: 1,200.

## Included records

- Three separate Company accounts with standard charts of accounts, fiscal years, cost centers and site warehouses.
- Customer/Supplier, 1,080 Employee, Department, Designation, material and service Item masters.
- 86 Projects and 5 linked Tasks per project; 86 native Sales Orders with BOQ work-package rows.
- Partial progress Sales Invoices tied to their Sales Order BOQ rows; 95% due, 5% delayed retention (NOT a tax).
- 86 subcontract Purchase Orders with three BOQ packages; periodical linked contractor Purchase Invoices.
- Purchase Order -> Receipt -> Purchase Invoice -> Stock Entry (issue to project) -> supplier Payment Entry.
- Synthetic balanced capital opening Journal Entries and customer receipts with paid/part-paid/unpaid states.
- Optional Frappe HRMS salary structure, assignment, salary slips, two attendance days/month, leave allocations and aggregate payroll journals.
- 470 synthetic equipment Asset DRAFTS with distinct serial names and Asset Category (not booked or depreciated).
- Dedicated bilingual Sales Invoice print format watermarked as DEMO.
- Read-only audit for counts, General Ledger balance and unexpected non-simulated tax rates.

## Tax assumptions, checked November 2026

- Kuwait: no VAT regime implemented. DO NOT use 5% as real VAT.
- Qatar: General Tax Authority states no VAT implemented.
- Syria: no general VAT. Selective consumption expenditure fees and withholding depend on detailed items / law and are NOT assumed by this simulator. Planned new reforms are not enacted by default.

Country tax mode (default) generates an informational 0% row, which does NOT imply statutory zero-rating. Simulated tax mode adds some explicitly fictional 5% rows named SIMULATED - NOT LAW for report testing only. No real tax IDs, bank accounts, legal statements, return filings or historical FX conversions are supplied.

## Module entry points

- config.py — the reproducible dataset plan
- seed.py — guarded orchestration, master records
- taxes.py — tax templates and per-invoice treatment
- print_format.py — DEMO Arabic/English progress invoice
- contracts.py — BOQ Sales Order and retention
- subcontracts.py — subcontract BOQ order
- transactions.py — submitted progress and supplier invoices
- procurement.py — procurement, stock movement, supplier payment
- equipment.py — fixed-asset master drafts
- hrms_seed.py — optional payroll and leave simulation
- audit.py — read-only post-run verification

## Docker: image build prerequisite

The running official Docker image does not contain this fork or HRMS. Build a custom image from the official frappe_docker repository instead of copying code into live containers.

From a checkout of https://github.com/frappe/frappe_docker create apps.json:

~~~json
[
  {"url":"https://github.com/Barahariri/erpnext","branch":"feature/construction-enterprise-demo"},
  {"url":"https://github.com/frappe/hrms","branch":"version-16"}
]
~~~

The official framework uses branch version-16.

~~~bash
docker build --no-cache \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --secret=id=apps_json,src=apps.json \
  --tag=local/erpnext-construction-demo:16 \
  --file=images/layered/Containerfile .
~~~

Use this same custom image for your web, worker, scheduler and other Frappe application processes in Docker Compose; do not change MariaDB and Redis images. Compose paths and service names must be discovered on the actual server first. Do not run docker compose down -v.

Official documentation:
https://frappe.github.io/frappe_docker/02-setup/02-build-setup.html

## Running on a disposable test site

Use a temporary, isolated site that can be reset. The site in the user's listing was erp.yourdomain.com, but verify it is really disposable before any reset. Bench reinstall is destructive. This README does not run it.

~~~bash
docker exec erpnext-backend-1 bench version
docker exec erpnext-backend-1 bench --site erp.yourdomain.com list-apps

# After using the built image and optionally installing hrms:
docker exec erpnext-backend-1 bench --site erp.yourdomain.com set-config construction_demo_enabled 1

# Read-only preview:
docker exec erpnext-backend-1 bench --site erp.yourdomain.com execute erpnext.setup.construction_demo.seed.run

# Tiny pilot first:
docker exec erpnext-backend-1 bench --site erp.yourdomain.com execute \
  erpnext.setup.construction_demo.seed.run \
  --kwargs '{"dry_run":0,"scale":"pilot","phase":"all","tax_mode":"simulated","confirmation":"GENERATE_CONSTRUCTION_DEMO"}'

# Read-only validation:
docker exec erpnext-backend-1 bench --site erp.yourdomain.com execute \
  erpnext.setup.construction_demo.audit.report

# ONLY ON A REINSTALLED / SEPARATE DISPOSABLE SITE:
docker exec erpnext-backend-1 bench --site erp.yourdomain.com execute \
  erpnext.setup.construction_demo.seed.run \
  --kwargs '{"dry_run":0,"scale":"full","phase":"all","tax_mode":"country","confirmation":"GENERATE_CONSTRUCTION_DEMO"}'
~~~

If HRMS does not appear in site list-apps, installing the app into the custom image is not enough. Explicitly install it on the test site and migrate using the documented Bench procedure.

## Known integration-test limitations

This is code committed to GitHub, NOT a completed database population on the remote server. Before calling it validated: run the pilot; confirm company chart-of-account defaults, accepted tax rows, Sales Order percentage billing against linked order lines, purchase receipt and stock issue quantities, and HRMS salary slip submit. Check the audit's General Ledger balance and the print output, and test the full load without timeouts.

The generator uses multiple commits; it is deliberately not a single atomic transaction. It is designed to rerun safely with stable DEMO keys, but a fresh disposable site is recommended for a full clean replay.

HRMS salary slips are posted with a separate synthetic aggregate payroll Journal Entry; do NOT run a second Payroll Entry accrual for the same salary slips. Attendance covers two sample days/month and is not a complete daily timesheet. Draft assets have no depreciation/booked capital acquisition. Frappe's full regulatory and country-specific payroll localization has not been implemented. Restrict this mode to isolated testing.
