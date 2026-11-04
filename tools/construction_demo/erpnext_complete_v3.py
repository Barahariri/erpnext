"""ERPNext 16 construction demo - v3 completion pass for isolated site 'frontend'.

This script operates on the clean site ONLY, uses ERPNext doc insert/submit APIs,
and deliberately keeps accounting postings separate for each company's currency.
It *does not* pretend to seed every internal DocType or to certify tax/payroll.

Requires the bundled v2 base seeder to have completed successfully.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
import argparse
import json
import sys

import frappe
import erpnext_clean_multicompany_v2 as base

START_MONTHS = ("2026-09", "2026-10", "2026-11")
POST_DAYS = (18, 16, 1)  # November payments post no later than November 4.
CREATED = Counter()
REUSED = Counter()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def existing(doctype, key):
    return frappe.db.get_value(doctype, key, "name")


def build(doctype, key, payload, submit=False):
    """Idempotent by a stable business key; never silently rewrite existing docs."""
    name = existing(doctype, key)
    if name:
        doc = frappe.get_doc(doctype, name)
        require(doc.docstatus != 2, f"Cancelled existing {doctype}: {name}")
        if submit and doc.docstatus == 0:
            doc.submit()
        REUSED[doctype] += 1
        return doc
    doc = frappe.get_doc({"doctype": doctype, **payload})
    doc.insert(ignore_permissions=True)
    if submit:
        doc.submit()
    CREATED[doctype] += 1
    return doc


def company_currency(d):
    return d["currency"]


def project_doc(d, index):
    proj = d["projects"][index][0]
    name = existing("Project", {"company": d["company"], "project_name": proj})
    require(name, f"Missing project {d['abbr']}/{proj}")
    return frappe.get_doc("Project", name)


def account(d, label=None, account_type=None, root=None):
    filters = {"company": d["company"], "is_group": 0}
    if label:
        filters["account_name"] = label
    if account_type:
        filters["account_type"] = account_type
    if root:
        filters["root_type"] = root
    name = existing("Account", filters)
    require(name, f"Missing ledger {d['abbr']} {label or account_type or root}")
    return name


def new_account(d, number, label, kind, root_type="Asset"):
    old = existing("Account", {"company": d["company"], "account_name": label})
    if old:
        a = frappe.get_doc("Account", old)
        require(a.account_number == str(number) and not a.is_group, f"Account mismatch: {old}")
        return old
    collision = existing("Account", {"company": d["company"], "account_number": str(number)})
    require(not collision, f"Account number {number} already in use: {collision}")
    root = base.root_account(d["company"], root_type)
    return build("Account", {"company": d["company"], "account_name": label}, {
        "company": d["company"], "account_name": label, "account_number": str(number),
        "parent_account": root, "is_group": 0, "account_type": kind,
    }).name


def current_company_check():
    base.verify_site()
    require(set(frappe.get_installed_apps()) >= {"frappe", "erpnext", "hrms"}, "HRMS missing on NEW site")
    for d in base.DATA:
        require(frappe.db.exists("Company", d["company"]), f"Missing company {d['company']}")
        require(frappe.db.count("Project", {"company": d["company"]}) >= 3, "Base project seed incomplete")
        require(frappe.db.count("Account", {"company": d["company"]}) >= 30, "Base chart incomplete")


def setup_banking(d):
    """One *fictional* bank master/account per company, never real account details."""
    company = d["company"]
    bank_gl = existing("Account", {"company": company, "account_type": "Bank", "is_group": 0})
    if not bank_gl:
        bank_gl = new_account(d, 139001, "Operating Bank Ledger", "Bank")
    bank = build("Bank", {"bank_name": "Sample Clearing Bank"}, {"bank_name": "Sample Clearing Bank"})
    account_name = f"Operating Treasury {d['abbr']}"
    bank_doc = build("Bank Account", {"account_name": account_name, "bank": bank.name}, {
        "account_name": account_name, "bank": bank.name, "company": company, "account": bank_gl,
        "is_company_account": 1, "is_default": 1,
        "bank_account_no": f"TEST-ONLY-{d['abbr']}",
    })
    require(bank_doc.company == company and bank_doc.account == bank_gl, "Bank Account company/GL mismatch")
    if not frappe.db.get_value("Company", company, "default_bank_account"):
        frappe.db.set_value("Company", company, "default_bank_account", bank_gl)
    frappe.db.commit()
    print(f"BANKING: {d['abbr']} GL={bank_gl} account={bank_doc.name}", flush=True)
    return bank_gl, bank_doc.name


def setup_global_defaults():
    default = "Al Furqan Contracting"
    require(frappe.db.exists("Company", default), "Default company missing")
    frappe.db.set_single_value("Global Defaults", "default_company", default)
    frappe.defaults.set_global_default("company", default)
    frappe.defaults.set_user_default("company", default, user="Administrator")
    frappe.defaults.set_global_default("currency", "KWD")
    frappe.defaults.set_global_default("fiscal_year", "2026")
    frappe.db.commit()
    frappe.clear_cache()


def ensure_opening_capital(d, bank_gl):
    marker = f"{d['abbr']}-OPENING-FUND-2026"
    cash_value = {"AMQ": 900000, "AFK": 275000, "ALS": 480000000}[d["abbr"]]
    equity = account(d, root="Equity")
    doc = build("Journal Entry", {"company": d["company"], "user_remark": marker}, {
        "voucher_type": "Opening Entry", "naming_series": "ACC-JV-.YYYY.-",
        "posting_date": "2026-08-20", "company": d["company"], "is_opening": "Yes",
        "user_remark": marker,
        "accounts": [
            {"account": bank_gl, "debit_in_account_currency": cash_value, "credit_in_account_currency": 0},
            {"account": equity, "credit_in_account_currency": cash_value, "debit_in_account_currency": 0},
        ],
    }, submit=True)
    return doc.name


def month_date(month_index):
    return f"{START_MONTHS[month_index]}-{POST_DAYS[month_index]:02d}"


def next_date(value, n=2):
    return (date.fromisoformat(str(value)) + timedelta(days=n)).isoformat()


def month_invoice(d, project_index, month_index):
    company, currency, abbr = d["company"], d["currency"], d["abbr"]
    project = project_doc(d, project_index)
    day = month_date(month_index)
    so_key = f"{abbr}-CONTRACT-{project_index + 1:03d}"
    so = existing("Sales Order", {"company": company, "po_no": so_key})
    require(so, f"Sales Order missing: {so_key}")
    so_doc = frappe.get_doc("Sales Order", so)
    require(so_doc.docstatus == 1, f"Sales Order unsubmitted: {so}")
    marker = f"{abbr}-BILL-{project_index + 1:03d}-{START_MONTHS[month_index]}"
    income = account(d, "Progress Billing Revenue")
    budget = d["projects"][project_index][2]
    doc = build("Sales Invoice", {"company": company, "po_no": marker}, {
        "naming_series": "ACC-SINV-.YYYY.-", "company": company, "customer": so_doc.customer,
        "posting_date": day, "posting_time": "12:00:00", "set_posting_time": 1,
        "due_date": next_date(day, 30), "currency": currency, "conversion_rate": 1,
        "selling_price_list": f"DEMO {abbr} Selling",
        "price_list_currency": currency, "plc_conversion_rate": 1,
        "ignore_pricing_rule": 1,
        "project": project.name, "cost_center": project.cost_center,
        "po_no": marker, "po_date": day, "debit_to": account(d, account_type="Receivable"),
        "items": [{
            "item_code": "SRV-PROGRESS", "qty": 1, "rate": round(budget / 4, 2),
            "income_account": income, "project": project.name,
            "cost_center": project.cost_center,
            "sales_order": so_doc.name, "so_detail": so_doc.items[0].name,
        }],
    }, submit=True)
    require(doc.docstatus == 1 and doc.company == company, f"Invoice not submitted {marker}")
    return doc


def month_subcontract_invoice(d, project_index, month_index):
    company, currency, abbr = d["company"], d["currency"], d["abbr"]
    project = project_doc(d, project_index)
    day = month_date(month_index)
    po_key = f"{abbr}-SUBCON-{project_index + 1:03d}"
    po = existing("Purchase Order", {"company": company, "order_confirmation_no": po_key})
    require(po, f"Subcontract Purchase Order missing: {po_key}")
    po_doc = frappe.get_doc("Purchase Order", po)
    require(po_doc.docstatus == 1, f"Subcontract Purchase Order unsubmitted: {po}")
    bill_no = f"SC-{abbr}-{project_index+1:02d}-{START_MONTHS[month_index].replace('-', '')}"
    amount = d["projects"][project_index][2] * 0.20
    doc = build("Purchase Invoice", {"company": company, "supplier": po_doc.supplier, "bill_no": bill_no}, {
        "naming_series": "ACC-PINV-.YYYY.-", "company": company,
        "supplier": po_doc.supplier, "posting_date": day, "posting_time": "11:00:00",
        "set_posting_time": 1, "due_date": next_date(day, 30), "bill_date": day,
        "bill_no": bill_no, "project": project.name, "cost_center": project.cost_center,
        "currency": currency, "conversion_rate": 1,
        "buying_price_list": f"DEMO {abbr} Buying",
        "price_list_currency": currency, "plc_conversion_rate": 1,
        "ignore_pricing_rule": 1,
        "credit_to": account(d, account_type="Payable"),
        "items": [{
            "item_code": "SRV-SUBCON", "qty": .25, "rate": round(amount, 2),
            "purchase_order": po_doc.name, "po_detail": po_doc.items[0].name,
            "expense_account": account(d, "Subcontractor Works"),
            "project": project.name, "cost_center": project.cost_center,
        }],
    }, submit=True)
    require(doc.docstatus == 1 and doc.company == company, f"Purchase Invoice failed: {bill_no}")
    return doc


def month_material_receipt(d, project_index):
    """One real stock receipt per project, placed across Sep/Oct/Nov."""
    company, abbr, currency = d["company"], d["abbr"], d["currency"]
    project = project_doc(d, project_index)
    day = month_date(project_index)
    po_key = f"{abbr}-MATERIAL-{project_index + 1:03d}"
    po = existing("Purchase Order", {"company": company, "order_confirmation_no": po_key})
    require(po, f"Material Purchase Order missing: {po_key}")
    po_doc = frappe.get_doc("Purchase Order", po)
    line = po_doc.items[0]
    warehouse = existing("Warehouse", {"company": company, "warehouse_name": f"{d['projects'][project_index][1]} Project Store"})
    require(warehouse, f"Project warehouse missing: {d['abbr']}/{project.name}")
    ref = f"WH-{abbr}-{project_index+1:02d}-{START_MONTHS[project_index].replace('-', '')}"
    doc = build("Purchase Receipt", {"company": company, "supplier_delivery_note": ref}, {
        "naming_series": "MAT-PRE-.YYYY.-", "company": company,
        "supplier": po_doc.supplier, "supplier_delivery_note": ref,
        "posting_date": day, "posting_time": "10:00:00", "set_posting_time": 1,
        "currency": currency, "conversion_rate": 1,
        "buying_price_list": f"DEMO {abbr} Buying",
        "price_list_currency": currency, "plc_conversion_rate": 1,
        "ignore_pricing_rule": 1,
        "project": project.name,
        "cost_center": project.cost_center,
        "items": [{
            "item_code": line.item_code, "qty": line.qty, "received_qty": line.qty,
            "rate": line.rate, "warehouse": warehouse,
            "purchase_order": po_doc.name, "purchase_order_item": line.name,
            "project": project.name, "cost_center": project.cost_center,
        }],
    }, submit=True)
    require(doc.docstatus == 1, f"Purchase Receipt failed {ref}")
    return doc, warehouse



def month_material_invoice(d, project_index, receipt):
    """Real purchase invoice matched to a posted receipt/PO; no double stock receipt."""
    company, abbr = d["company"], d["abbr"]
    project = project_doc(d, project_index)
    day = next_date(month_date(project_index))
    bill_no = f"MAT-{abbr}-{project_index + 1:02d}-{START_MONTHS[project_index].replace('-', '')}"
    receipt_row = receipt.items[0]
    doc = build("Purchase Invoice", {"company": company, "supplier": receipt.supplier, "bill_no": bill_no}, {
        "naming_series": "ACC-PINV-.YYYY.-", "company": company,
        "supplier": receipt.supplier, "bill_no": bill_no, "bill_date": day,
        "posting_date": day, "posting_time": "15:00:00", "set_posting_time": 1,
        "due_date": next_date(day, 30), "currency": d["currency"], "conversion_rate": 1,
        "buying_price_list": f"DEMO {abbr} Buying",
        "price_list_currency": d["currency"], "plc_conversion_rate": 1,
        "ignore_pricing_rule": 1,
        "project": project.name, "cost_center": project.cost_center,
        "credit_to": account(d, account_type="Payable"),
        "items": [{
            "item_code": receipt_row.item_code, "qty": receipt_row.qty, "rate": receipt_row.rate,
            "warehouse": receipt_row.warehouse, "purchase_receipt": receipt.name,
            "pr_detail": receipt_row.name, "purchase_order": receipt_row.purchase_order,
            "po_detail": receipt_row.purchase_order_item,
            "project": project.name, "cost_center": project.cost_center,
        }],
    }, submit=True)
    require(doc.docstatus == 1, f"Unsubmitted material invoice {bill_no}")
    return doc

def month_material_issue(d, project_index, warehouse, receipt):
    company, abbr = d["company"], d["abbr"]
    project = project_doc(d, project_index)
    ref = f"MATERIAL ISSUE {abbr}-{project_index+1:02d}-{START_MONTHS[project_index]}"
    row = receipt.items[0]
    qty = min(8, max(1, int(float(row.qty) / 3)))
    doc = build("Stock Entry", {"company": company, "remarks": ref}, {
        "naming_series": "MAT-STE-.YYYY.-", "company": company,
        "stock_entry_type": "Material Issue", "purpose": "Material Issue",
        "posting_date": next_date(month_date(project_index)),
        "posting_time": "14:00:00", "set_posting_time": 1,
        "project": project.name, "cost_center": project.cost_center,
        "remarks": ref,
        "items": [{
            "item_code": row.item_code, "qty": qty, "s_warehouse": warehouse,
            "project": project.name, "cost_center": project.cost_center,
            "expense_account": account(d, "Construction Materials Consumed"),
        }],
    }, submit=True)
    require(doc.docstatus == 1, f"Stock Entry not submitted: {ref}")
    return doc


def sample_payment(d, invoice, bank_gl, month_index):
    abbr, company, currency = d["abbr"], d["company"], d["currency"]
    marker = f"{abbr}-RECEIPT-{START_MONTHS[month_index]}"
    amount = round(float(invoice.grand_total) * 0.46, 2)
    require(amount > 0, "Invoice total is empty")
    day = next_date(month_date(month_index), 3)
    doc = build("Payment Entry", {"company": company, "reference_no": marker}, {
        "naming_series": "ACC-PAY-.YYYY.-", "payment_type": "Receive",
        "posting_date": day, "company": company, "party_type": "Customer",
        "party": invoice.customer, "reference_no": marker,
        "reference_date": day,
        "paid_from": invoice.debit_to, "paid_to": bank_gl,
        "paid_from_account_currency": currency, "paid_to_account_currency": currency,
        "paid_amount": amount, "received_amount": amount,
        "source_exchange_rate": 1, "target_exchange_rate": 1,
        "references": [{"reference_doctype": "Sales Invoice", "reference_name": invoice.name,
                        "allocated_amount": amount}],
    }, submit=True)
    require(doc.docstatus == 1, f"Payment not submitted: {marker}")
    return doc


def sample_bank_transaction(d, bank_account, payment, month_index):
    company, abbr = d["company"], d["abbr"]
    ref = f"BANK-STMT-{abbr}-{START_MONTHS[month_index]}"
    doc = build("Bank Transaction", {"bank_account": bank_account, "transaction_id": ref}, {
        "naming_series": "ACC-BTN-.YYYY.-", "company": company,
        "bank_account": bank_account, "currency": d["currency"],
        "date": next_date(month_date(month_index), 3),
        "transaction_id": ref, "reference_number": payment.reference_no,
        "description": f"Sample customer collection - {payment.party}",
        "deposit": payment.received_amount, "withdrawal": 0,
    }, submit=True)
    require(doc.docstatus == 1, f"Bank Transaction not submitted: {ref}")
    return doc


def transactions_for_company(d):
    bank_gl, bank_acc = setup_banking(d)
    ensure_opening_capital(d, bank_gl)
    frappe.db.commit()
    for m in range(3):
        payment_invoice = None
        for i in range(3):
            si = month_invoice(d, i, m)
            month_subcontract_invoice(d, i, m)
            if i == 0:
                payment_invoice = si
        payment = sample_payment(d, payment_invoice, bank_gl, m)
        sample_bank_transaction(d, bank_acc, payment, m)
        receipt, wh = month_material_receipt(d, m)
        month_material_invoice(d, m, receipt)
        month_material_issue(d, m, wh, receipt)
        frappe.db.commit()
        print(f"POSTED: {d['abbr']} {START_MONTHS[m]} sales=3 purchase-invoices=4 payments=1 stock-receipts=1 material-issues=1 bank-statements=1", flush=True)


def hr_samples(d):
    """HRMS: distinct staff, attendance; payroll templates with non-posted samples."""
    company, abbr, currency = d["company"], d["abbr"], d["currency"]
    for i, name in enumerate(("2026-09-07", "2026-09-14", "2026-09-21",
                              "2026-10-05", "2026-10-12", "2026-10-19",
                              "2026-11-02", "2026-11-03")):
        # The date is a fixture sample, not a complete work-month or attendance policy.
        for emp in frappe.get_all("Employee", {"company": company, "status": "Active"}, ["name"], order_by="name asc", limit=6):
            build("Attendance", {"employee": emp.name, "attendance_date": name, "company": company}, {
                "naming_series": "HR-ATT-.YYYY.-", "employee": emp.name,
                "attendance_date": name, "company": company,
                "status": "Present" if i != 5 else "Half Day",
            }, submit=True)
        frappe.db.commit()
    # HR salary templates are DEMO configuration; do not submit fake payroll journal entries.
    component = build("Salary Component", {"salary_component": "Sample Basic Salary"}, {
        "salary_component": "Sample Basic Salary", "salary_component_abbr": "SBS",
        "type": "Earning", "depends_on_payment_days": 0,
    })
    structure_name = f"Standard Monthly Payroll - {abbr}"
    structure = build("Salary Structure", {"name": structure_name}, {
        "name": structure_name, "company": company, "currency": currency,
        "payroll_frequency": "Monthly", "is_active": "Yes",
        "salary_slip_based_on_timesheet": 0,
        "earnings": [{"salary_component": component.name, "amount": {"AMQ": 8800, "AFK": 1000, "ALS": 5000000}[abbr]}],
    }, submit=True)
    # For one salaried office employee, generate an assignment to test Salary Structure link.
    emp = frappe.db.get_value("Employee", {"company": company, "designation": "Accountant"}, "name")
    if emp:
        amount = {"AMQ": 8800, "AFK": 1000, "ALS": 5000000}[abbr]
        build("Salary Structure Assignment", {
            "employee": emp, "salary_structure": structure.name, "from_date": "2026-08-01", "docstatus": ["<", 2],
        }, {
            "employee": emp, "salary_structure": structure.name, "from_date": "2026-08-01",
            "company": company, "currency": currency, "base": amount,
        }, submit=True)
    frappe.db.commit()
    print(f"HR READY: {abbr} attendance samples and payroll structure", flush=True)


def create_asset_samples(d):
    """Draft Asset records; no invented purchase GL or depreciation postings."""
    company, abbr = d["company"], d["abbr"]
    fixed = account(d, "Heavy Construction Equipment")
    accum = account(d, "Accumulated Plant Depreciation")
    dep = account(d, "Equipment Depreciation - Projects")
    category_name = "Construction Machinery Sample"
    cat_name = existing("Asset Category", {"asset_category_name": category_name})
    if not cat_name:
        accounts = []
        for x in base.DATA:
            accounts.append({
                "company_name": x["company"],
                "fixed_asset_account": account(x, "Heavy Construction Equipment"),
                "accumulated_depreciation_account": account(x, "Accumulated Plant Depreciation"),
                "depreciation_expense_account": account(x, "Equipment Depreciation - Projects"),
            })
        category = build("Asset Category", {"asset_category_name": category_name}, {
            "asset_category_name": category_name, "accounts": accounts,
        })
    else:
        category = frappe.get_doc("Asset Category", cat_name)
        require({r.company_name for r in category.accounts} >= {x["company"] for x in base.DATA},
                "Asset Category missing multi-company accounts")
    item = build("Item", {"item_code": "MACH-EXCAVATOR-220"}, {
        "item_code": "MACH-EXCAVATOR-220", "item_name": "Hydraulic Excavator 22 Ton",
        "item_group": "Raw Material", "stock_uom": "Nos", "is_stock_item": 0,
        "is_fixed_asset": 1, "auto_create_assets": 0, "is_sales_item": 0,
        "is_purchase_item": 1, "asset_category": category.name,
    })
    project = project_doc(d, 0)
    location = build("Location", {"location_name": f"Construction Equipment Yard {abbr}"}, {
        "location_name": f"Construction Equipment Yard {abbr}", "is_group": 0,
    })
    value = {"AMQ": 225000, "AFK": 34500, "ALS": 450000000}[abbr]
    doc = build("Asset", {"asset_name": f"Crawler Excavator {abbr} 01", "company": company}, {
        "naming_series": "ACC-ASS-.YYYY.-", "asset_name": f"Crawler Excavator {abbr} 01",
        "item_code": item.name, "asset_category": category.name,
        "asset_type": "Existing Asset", "asset_owner": "Company", "asset_owner_company": company,
        "company": company, "location": location.name, "cost_center": project.cost_center,
        "purchase_date": "2025-01-10", "available_for_use_date": "2025-01-20",
        "purchase_amount": value, "net_purchase_amount": value,
        "calculate_depreciation": 0,
    }, submit=False)
    frappe.db.commit()
    print(f"ASSET DRAFT: {abbr} {doc.name} (no GL impact)", flush=True)


def nov_fleet_samples(d):
    # Base V2 creates September/October logs, extend coverage into November.
    abbr = d["abbr"]
    driver = frappe.db.get_value("Employee", {"employee_number": f"{abbr}-DRV-001"}, "name")
    require(driver, f"Fleet driver missing for {abbr}")
    vehicle_name = f"{abbr}-FLT-001"
    require(frappe.db.exists("Vehicle", vehicle_name), "Fleet vehicle missing")
    project = frappe.db.get_value("Vehicle", vehicle_name, "custom_assigned_project")
    cc = frappe.db.get_value("Vehicle", vehicle_name, "custom_assigned_cost_center")
    require(frappe.db.get_value("Project", project, "company") == d["company"], "Fleet project company mismatch")
    required_date = "2026-11-03"
    key = {"license_plate": vehicle_name, "date": required_date}
    if existing("Vehicle Log", key):
        log = frappe.get_doc("Vehicle Log", existing("Vehicle Log", key))
        require(log.docstatus == 1, "Existing November vehicle log is draft")
    else:
        old_km = int(frappe.db.get_value("Vehicle", vehicle_name, "last_odometer") or 0)
        log = build("Vehicle Log", key, {
            "naming_series": "HR-VLOG-.YYYY.-", "license_plate": vehicle_name,
            "employee": driver, "date": required_date, "last_odometer": old_km,
            "odometer": old_km + 145, "fuel_qty": 32, "price": base.FLEET_FUEL_PRICE[abbr],
            "supplier": existing("Supplier", {"supplier_name": base.FLEET_FUEL_SUPPLIERS[abbr]}),
            "invoice": f"FUEL-{abbr}-20261103", "custom_project": project,
            "custom_cost_center": cc, "custom_route_from": d["projects"][0][1],
            "custom_route_to": d["projects"][1][1],
            "custom_trip_purpose": "Site materials transfer", "custom_trip_distance_km": 145,
        }, submit=True)
    frappe.db.commit()
    print(f"FLEET NOV: {abbr} {log.name}", flush=True)



def dashboard_samples(d):
    """Actual ERPNext Dashboard Charts filtered to ONE company and submitted rows."""
    company, abbr = d["company"], d["abbr"]
    titles = (
        ("Sales Invoice", "base_grand_total", "Sales Invoices"),
        ("Purchase Invoice", "base_grand_total", "Supplier Invoices"),
        ("Payment Entry", "base_paid_amount", "Collections"),
    )
    chart_names = []
    for doctype, value, label in titles:
        chart_name = f"{abbr} Construction - {label}"
        filters = [[doctype, "company", "=", company], [doctype, "docstatus", "=", 1]]
        chart = build("Dashboard Chart", {"chart_name": chart_name}, {
            "chart_name": chart_name, "chart_type": "Sum", "document_type": doctype,
            "based_on": "posting_date", "value_based_on": value,
            "timeseries": 1, "timespan": "Last Year", "time_interval": "Monthly",
            "type": "Bar", "filters_json": json.dumps(filters), "is_public": 1,
        })
        require(json.loads(chart.filters_json) == filters,
                f"Dashboard Chart filters mismatch for {chart_name}")
        chart_names.append(chart.name)
    dash_name = f"Construction Performance {abbr}"
    dashboard = build("Dashboard", {"dashboard_name": dash_name}, {
        "dashboard_name": dash_name,
        "charts": [{"chart": name} for name in chart_names],
    })
    require({r.chart for r in dashboard.charts} == set(chart_names),
            f"Dashboard has wrong charts: {dash_name}")
    # Get the real generated chart data, not a screenshot or synthetic KPI.
    from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as fetch_chart
    for chart_name in chart_names:
        values = fetch_chart(chart_name=chart_name)
        require(values is not None, f"Chart returned no result: {chart_name}")
    frappe.db.commit()
    print(f"DASHBOARD READY: {abbr} {dash_name}", flush=True)

def audit():
    report = {"site": "frontend", "companies": {}, "issues": [], "warnings": []}
    gl = "GL Entry"
    checks = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Purchase Receipt", "Stock Entry")
    for d in base.DATA:
        company, abbr = d["company"], d["abbr"]
        result = {"currency": d["currency"], "months": {}, "accounts": {}, "masters": {}, "banking": {}}
        ledger = frappe.get_all("Account", {"company": company}, ["name", "account_number"])
        numbers = [x.account_number for x in ledger]
        if not ledger or any(not x or len(str(x)) != 6 for x in numbers) or len(set(numbers)) != len(numbers):
            report["issues"].append(f"{abbr}: incomplete/duplicate account_number")
        result["accounts"] = {"total": len(ledger), "numbered": sum(bool(x) for x in numbers)}
        balances = frappe.db.sql(
            "SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` WHERE company=%s AND IFNULL(is_cancelled,0)=0",
            (company,), as_list=True,
        )
        gl_diff = float(balances[0][0] or 0)
        result["gl_balance_difference"] = round(gl_diff, 2)
        if abs(gl_diff) > 0.1:
            report["issues"].append(f"{abbr}: unbalanced GL {gl_diff}")
        result["masters"] = {
            "projects": frappe.db.count("Project", {"company": company}),
            "employees": frappe.db.count("Employee", {"company": company}),
            "vehicles": frappe.db.count("Vehicle", {"company": company}),
            "attendance_submitted": frappe.db.count("Attendance", {"company": company, "docstatus": 1}),
            "assets_draft": frappe.db.count("Asset", {"company": company, "docstatus": 0}),
            "salary_structures": frappe.db.count("Salary Structure", {"company": company, "docstatus": 1}),
            "tasks": frappe.db.count("Task", {"company": company}),
            "cost_centers": frappe.db.count("Cost Center", {"company": company}),
            "warehouse": frappe.db.count("Warehouse", {"company": company}),
        }
        result["charts"] = frappe.db.count("Dashboard Chart", {
            "chart_name": ["like", f"{abbr} Construction - %"]
        })
        if result["charts"] < 3:
            report["issues"].append(f"{abbr}: company performance charts missing")
        result["banking"] = {
            "company_bank_accounts": frappe.db.count("Bank Account", {"company": company, "is_company_account": 1}),
            "bank_transactions": frappe.db.count("Bank Transaction", {"company": company, "docstatus": 1}),
        }
        if result["banking"]["company_bank_accounts"] == 0:
            report["issues"].append(f"{abbr}: no company bank account")
        for index, month in enumerate(START_MONTHS):
            start = f"{month}-01"
            stop = f"{START_MONTHS[index + 1]}-01" if index < 2 else "2026-12-01"
            counts = {}
            for dt in checks:
                filters = {"company": company, "docstatus": 1, "posting_date": ["between", [start, next_date(stop, -1)]]}
                counts[dt] = frappe.db.count(dt, filters)
                if counts[dt] == 0:
                    report["issues"].append(f"{abbr}: missing posted {dt} {month}")
            counts["Vehicle Log"] = frappe.db.count("Vehicle Log", {
                "license_plate": ["like", f"{abbr}-FLT-%"], "docstatus": 1,
                "date": ["between", [start, next_date(stop, -1)]],
            })
            if counts["Vehicle Log"] == 0:
                report["issues"].append(f"{abbr}: no fleet log {month}")
            result["months"][month] = counts
        if result["masters"]["projects"] < 3 or result["masters"]["employees"] < 15:
            report["issues"].append(f"{abbr}: incomplete project/employee master")
        if result["masters"]["salary_structures"] == 0:
            report["issues"].append(f"{abbr}: no salary structure")
        if result["masters"]["attendance_submitted"] == 0:
            report["issues"].append(f"{abbr}: no HR attendance")
        if result["masters"]["assets_draft"] == 0:
            report["issues"].append(f"{abbr}: no Asset sample")
        report["companies"][abbr] = result
    report["warnings"].append("All companies, people, contract values, banks and dates are fictitious training data.")
    report["warnings"].append("Salary structure and asset records are examples, not posted payroll or asset depreciation.")
    report["warnings"].append("November is sampled to November 3; it is NOT a completed month.")
    return report


def execute(phase):
    frappe.init(site="frontend", sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")
    try:
        current_company_check()
        if phase in ("all", "banking"):
            for d in base.DATA:
                setup_banking(d)
            setup_global_defaults()
        if phase in ("all", "transactions"):
            for d in base.DATA:
                transactions_for_company(d)
        if phase in ("all", "hr"):
            for d in base.DATA:
                hr_samples(d)
        if phase in ("all", "assets"):
            for d in base.DATA:
                create_asset_samples(d)
        if phase in ("all", "fleet"):
            for d in base.DATA:
                nov_fleet_samples(d)
        if phase in ("all", "dashboard"):
            for d in base.DATA:
                dashboard_samples(d)
        report = audit()
        print("FINAL_AUDIT_JSON_BEGIN")
        print(json.dumps({"created": dict(CREATED), "reused": dict(REUSED), "report": report},
                         indent=2, ensure_ascii=False, default=str))
        print("FINAL_AUDIT_JSON_END")
        if phase == "all":
            require(not report["issues"], "INCOMPLETE: audit issues remain, do not mark READY")
            print("CONSTRUCTION_DEMO_V3_READY", flush=True)
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "banking", "transactions", "hr", "assets", "fleet", "dashboard", "audit"), default="all")
    execute(parser.parse_args().phase)
