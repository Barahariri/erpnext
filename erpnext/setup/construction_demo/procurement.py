"""Purchase -> Receipt -> Invoice -> Payment -> Material Issue simulation.

Every step uses the public ERPNext document APIs so Stock Ledger and GL
reconciliation stay with ERPNext. Keys are persisted on source documents.
"""
from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import add_days, add_months, getdate

from erpnext.setup.construction_demo.config import COMPANIES, START_DATE, END_DATE, MATERIAL_COUNT, PROJECT_CATALOG, scaled


def _get_doc(doctype: str, filters: dict):
    name = frappe.db.get_value(doctype, filters, "name")
    return frappe.get_doc(doctype, name) if name else None


def _supplier(seed, plan, index):
    label = seed.supplier_label(plan, 1 + (index % scaled(plan.suppliers, seed.scale)))
    name = frappe.db.get_value("Supplier", {"supplier_name": label}, "name")
    if not name:
        frappe.throw("Missing demo supplier " + label)
    return name


def _site_warehouse(plan, index):
    site = PROJECT_CATALOG[plan.abbr][index - 1].district
    name = frappe.db.get_value(
        "Warehouse",
        {
            "warehouse_name": f"DEMO {plan.abbr} PROJECT {index:03d} {site}",
            "company": plan.name,
        },
        "name",
    )
    if not name:
        frappe.throw("Missing warehouse for " + plan.name)
    return name


def _purchase_order(seed, plan, project, index, month, posting):
    marker = f"DEMO-{plan.abbr}-STOCK-{index:03d}-{month:02d}"
    po = _get_doc("Purchase Order", {"company": plan.name, "order_confirmation_no": marker})
    if po:
        seed.existing["Purchase Order"] += 1
        if po.docstatus == 0:
            po.submit()
        return po

    site = _site_warehouse(plan, index)
    supplier = _supplier(seed, plan, index + month)
    multiplier = {"KRC": 1, "RDC": 10, "MSE": 100000}[plan.abbr]
    items = []
    material_total = scaled(MATERIAL_COUNT, seed.scale)
    for j in range(5):
        code = f"DEMO-MAT-{1 + ((index * 23 + month * 17 + j * 31) % material_total):04d}"
        items.append({
            "item_code": code,
            "qty": 12 + ((index * 3 + j * 11) % 25),
            "rate": (3 + (j * 7 + index % 9)) * multiplier,
            "uom": "Nos",
            "warehouse": site,
            "schedule_date": add_days(posting, 4),
            "project": project,
            "cost_center": seed.default_cost_center(plan.name),
        })
    po = frappe.get_doc({
        "doctype": "Purchase Order",
        "naming_series": "PUR-ORD-.YYYY.-",
        "company": plan.name,
        "supplier": supplier,
        "transaction_date": posting,
        "schedule_date": add_days(posting, 4),
        "order_confirmation_no": marker,
        "order_confirmation_date": posting,
        "currency": plan.currency,
        "conversion_rate": 1,
        "buying_price_list": f"DEMO {plan.abbr} Buying",
        "price_list_currency": plan.currency,
        "plc_conversion_rate": 1,
        "project": project,
        "cost_center": seed.default_cost_center(plan.name),
        "set_warehouse": site,
        "items": items,
    })
    from erpnext.setup.construction_demo.taxes import apply_taxes
    apply_taxes(po, plan, mode=seed.tax_mode, simulated=(month % 3 == 0))
    po.insert(ignore_permissions=True)
    po.submit()
    seed.created["Purchase Order"] += 1
    return po


def _receipt(seed, plan, po, month, posting):
    existing = frappe.db.get_value(
        "Purchase Receipt Item",
        {"purchase_order": po.name, "parenttype": "Purchase Receipt"},
        "parent",
    )
    if existing:
        seed.existing["Purchase Receipt"] += 1
        pr = frappe.get_doc("Purchase Receipt", existing)
        if pr.docstatus == 0:
            pr.submit()
        return pr

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    pr = make_purchase_receipt(po.name)
    pr.naming_series = "MAT-PRE-.YYYY.-"
    pr.posting_date = posting
    pr.posting_time = "10:30:00"
    pr.set_posting_time = 1
    from erpnext.setup.construction_demo.taxes import apply_taxes
    apply_taxes(pr, plan, mode=seed.tax_mode, simulated=(month % 3 == 0))
    pr.insert(ignore_permissions=True)
    pr.submit()
    seed.created["Purchase Receipt"] += 1
    return pr


def _receipt_invoice(seed, plan, receipt, month, posting):
    existing = frappe.db.get_value(
        "Purchase Invoice Item",
        {"purchase_receipt": receipt.name, "parenttype": "Purchase Invoice"},
        "parent",
    )
    if existing:
        seed.existing["Purchase Invoice"] += 1
        inv = frappe.get_doc("Purchase Invoice", existing)
        if inv.docstatus == 0:
            inv.submit()
        return inv

    from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

    inv = make_purchase_invoice(receipt.name)
    inv.naming_series = "ACC-PINV-.YYYY.-"
    inv.set_posting_time = 1
    inv.posting_date = posting
    inv.posting_time = "10:45:00"
    inv.bill_no = f"DEMO-BILL-{receipt.name}"
    inv.bill_date = posting
    inv.due_date = add_days(posting, 30)
    from erpnext.setup.construction_demo.taxes import apply_taxes
    apply_taxes(inv, plan, mode=seed.tax_mode, simulated=(month % 3 == 0))
    inv.insert(ignore_permissions=True)
    inv.submit()
    seed.created["Purchase Invoice"] += 1
    return inv


def _consume(seed, plan, receipt, project, posting):
    marker = f"DEMO-STOCK-ISSUE-{receipt.name}"
    existing = _get_doc(
        "Stock Entry", {"company": plan.name, "remarks": marker}
    )
    if existing:
        seed.existing["Stock Entry"] += 1
        if existing.docstatus == 0:
            existing.submit()
        return existing

    stock_rows = []
    for r in receipt.items:
        stock_rows.append({
            "item_code": r.item_code,
            "qty": r.qty,
            "s_warehouse": r.warehouse,
            "uom": r.uom,
            "conversion_factor": 1,
            "expense_account": frappe.db.get_value(
                "Company", plan.name, "default_expense_account"
            ),
            "cost_center": seed.default_cost_center(plan.name),
            "project": project,
        })
    doc = frappe.get_doc({
        "doctype": "Stock Entry",
        "naming_series": "MAT-STE-.YYYY.-",
        "company": plan.name,
        "stock_entry_type": "Material Issue",
        "purpose": "Material Issue",
        "set_posting_time": 1,
        "posting_date": posting,
        "posting_time": "11:00:00",
        "project": project,
        "cost_center": seed.default_cost_center(plan.name),
        "remarks": marker,
        "items": stock_rows,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Stock Entry"] += 1
    return doc


def _supplier_payment(seed, plan, invoice, posting):
    marker = f"DEMO-SUPPLIER-PAY-{invoice.name}"
    existing = _get_doc(
        "Payment Entry", {"company": plan.name, "reference_no": marker}
    )
    if existing:
        seed.existing["Payment Entry"] += 1
        if existing.docstatus == 0:
            existing.submit()
        return

    amount = round(float(invoice.grand_total) * 0.7, 2)
    account = frappe.db.get_value("Company", plan.name, "default_cash_account")
    payable = frappe.db.get_value("Company", plan.name, "default_payable_account")
    if not account or not payable:
        frappe.throw("Missing cash/payable accounts for " + plan.name)
    doc = frappe.get_doc({
        "doctype": "Payment Entry",
        "naming_series": "ACC-PAY-.YYYY.-",
        "payment_type": "Pay",
        "company": plan.name,
        "party_type": "Supplier",
        "party": invoice.supplier,
        "posting_date": posting,
        "reference_date": posting,
        "reference_no": marker,
        "paid_from": account,
        "paid_to": payable,
        "paid_from_account_currency": plan.currency,
        "paid_to_account_currency": plan.currency,
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "references": [{
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "allocated_amount": amount,
        }],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Payment Entry"] += 1


def seed_procurement(seed):
    cutoff = getdate(END_DATE)
    for plan in COMPANIES:
        for index in range(1, scaled(plan.projects, seed.scale) + 1):
            label = seed.project_label(plan, index)
            project = frappe.db.get_value(
                "Project", {"project_name": label, "company": plan.name}, "name"
            )
            if not project:
                frappe.throw("Missing project " + label)
            start = add_months(getdate(START_DATE), (index * 7) % 28)
            for month in (1, 3, 5, 7):
                posting = add_months(start, month)
                posting = posting.replace(day=5)
                if posting > cutoff or add_days(posting, 4) > cutoff:
                    continue
                po = _purchase_order(seed, plan, project, index, month, posting)
                received = _receipt(seed, plan, po, month, add_days(posting, 4))
                inv = _receipt_invoice(seed, plan, received, month, add_days(posting, 5))
                if add_days(posting, 15) <= cutoff:
                    _consume(seed, plan, received, project, add_days(posting, 15))
                if add_days(posting, 20) <= cutoff:
                    _supplier_payment(seed, plan, inv, add_days(posting, 20))
            frappe.db.commit()
