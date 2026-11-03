"""Historically dated accounting simulation for the construction demo.

Uses ERPNext documents and submit hooks, never direct GL Entry writes.
Only operates when the site is explicitly opted in via seed.run().
The first pilot must be validated before running full-scale transactions.
"""
from datetime import timedelta

import frappe
from frappe.utils import add_days, add_months, getdate

from erpnext.setup.construction_demo.config import COMPANIES, START_DATE, END_DATE, billing_cycles, scaled


def _account(plan, fieldname: str) -> str:
    account = frappe.db.get_value("Company", plan.name, fieldname)
    if not account:
        frappe.throw(f"{plan.abbr} missing Company.{fieldname}; configure the chart of accounts.")
    return account


def _ensure_opening_cash(seed, plan):
    marker = f"DEMO-{plan.abbr}-OPENING-CAPITAL-2023"
    existing = frappe.db.exists(
        "Journal Entry", {"company": plan.name, "user_remark": marker}
    )
    if existing:
        seed.existing["Journal Entry"] += 1
        doc = frappe.get_doc("Journal Entry", existing)
        if doc.docstatus == 0:
            doc.submit()
        return

    cash = _account(plan, "default_cash_account")
    equity = frappe.db.get_value(
        "Account",
        {"company": plan.name, "root_type": "Equity", "is_group": 0},
        "name",
    )
    if not equity:
        frappe.throw("No leaf Equity account for " + plan.name)

    # Each company books fictional owner funding, balanced in its own currency.
    amount = {"KRC": 3_000_000, "RDC": 15_000_000, "MSE": 900_000_000}[plan.abbr]
    doc = frappe.get_doc({
        "doctype": "Journal Entry",
        "naming_series": "ACC-JV-.YYYY.-",
        "voucher_type": "Opening Entry",
        "posting_date": START_DATE,
        "company": plan.name,
        "is_opening": "Yes",
        "user_remark": marker,
        "accounts": [
            {"account": cash, "debit_in_account_currency": amount, "credit_in_account_currency": 0},
            {"account": equity, "debit_in_account_currency": 0, "credit_in_account_currency": amount},
        ],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Journal Entry"] += 1


def _invoice_key(plan, index: int, cycle: int, kind: str) -> str:
    return f"DEMO-{plan.abbr}-PRJ-{index:03d}-{kind}-{cycle:02d}"


def _ensure_sales_invoice(seed, plan, project, customer, sales_order, index, cycle, posting, amount):
    ref = _invoice_key(plan, index, cycle, "S")
    existing = frappe.db.exists(
        "Sales Invoice", {"company": plan.name, "po_no": ref}
    )
    if existing:
        seed.existing["Sales Invoice"] += 1
        invoice = frappe.get_doc("Sales Invoice", existing)
        if invoice.docstatus == 0:
            invoice.submit()
        return invoice

    doc = frappe.get_doc({
        "doctype": "Sales Invoice",
        "naming_series": "ACC-SINV-.YYYY.-",
        "company": plan.name,
        "customer": customer,
        "project": project,
        "posting_date": posting,
        "posting_time": "12:00:00",
        "set_posting_time": 1,
        "due_date": add_days(posting, 45),
        "po_no": ref,
        "po_date": posting,
        "currency": plan.currency,
        "conversion_rate": 1,
        "selling_price_list": f"DEMO {plan.abbr} Selling",
        "price_list_currency": plan.currency,
        "plc_conversion_rate": 1,
        "debit_to": _account(plan, "default_receivable_account"),
        "cost_center": frappe.db.get_value("Project", project, "cost_center"),
        "payment_terms_template": "DEMO Construction 95pct + 5pct Retention",
        "remarks": (
            f"DEMO progress #{cycle}: contract {sales_order.name}; "
            "5% guarantee retention is a deferred receivable, not a tax."
        ),
        "items": __progress_lines(seed, plan, sales_order, amount),
    })
    from erpnext.setup.construction_demo.taxes import apply_taxes
    # Real country scenario 0% non-VAT; explicit fictional 5% on test cycles only.
    apply_taxes(doc, plan, mode=seed.tax_mode, simulated=(cycle % 4 == 0))
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Sales Invoice"] += 1
    return doc


def _ensure_purchase_invoice(seed, plan, project, supplier, subcontract, index, cycle, posting, amount):
    ref = _invoice_key(plan, index, cycle, "P")
    existing = frappe.db.exists(
        "Purchase Invoice", {"company": plan.name, "bill_no": ref, "supplier": supplier}
    )
    if existing:
        seed.existing["Purchase Invoice"] += 1
        doc = frappe.get_doc("Purchase Invoice", existing)
        if doc.docstatus == 0:
            doc.submit()
        return doc

    doc = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "naming_series": "ACC-PINV-.YYYY.-",
        "company": plan.name,
        "supplier": supplier,
        "project": project,
        "posting_date": posting,
        "posting_time": "11:00:00",
        "set_posting_time": 1,
        "due_date": add_days(posting, 30),
        "bill_no": ref,
        "bill_date": posting,
        "currency": plan.currency,
        "conversion_rate": 1,
        "buying_price_list": f"DEMO {plan.abbr} Buying",
        "price_list_currency": plan.currency,
        "plc_conversion_rate": 1,
        "credit_to": _account(plan, "default_payable_account"),
        "cost_center": frappe.db.get_value("Project", project, "cost_center"),
        "remarks": "DEMO ONLY: fictional subcontractor progress expense.",
        "items": __subcontract_lines(seed, plan, subcontract, amount, cycle),
    })
    from erpnext.setup.construction_demo.taxes import apply_taxes
    apply_taxes(doc, plan, mode=seed.tax_mode, simulated=(cycle % 6 == 0))
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Purchase Invoice"] += 1
    return doc


def _ensure_customer_receipt(seed, plan, invoice, index, cycle, posting, fraction):
    if invoice.docstatus != 1:
        return
    marker = _invoice_key(plan, index, cycle, "PAY")
    existing = frappe.db.exists(
        "Payment Entry", {"company": plan.name, "reference_no": marker}
    )
    if existing:
        seed.existing["Payment Entry"] += 1
        doc = frappe.get_doc("Payment Entry", existing)
        if doc.docstatus == 0:
            doc.submit()
        return

    amount = round(float(invoice.grand_total) * fraction, 2)
    if amount <= 0:
        return
    doc = frappe.get_doc({
        "doctype": "Payment Entry",
        "naming_series": "ACC-PAY-.YYYY.-",
        "payment_type": "Receive",
        "company": plan.name,
        "party_type": "Customer",
        "party": invoice.customer,
        "posting_date": posting,
        "reference_date": posting,
        "reference_no": marker,
        "mode_of_payment": "Cash",
        "paid_from": invoice.debit_to,
        "paid_to": _account(plan, "default_cash_account"),
        "paid_from_account_currency": plan.currency,
        "paid_to_account_currency": plan.currency,
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": amount,
        }],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Payment Entry"] += 1


def __subcontract_lines(seed, plan, order, amount, cycle):
    from erpnext.setup.construction_demo.subcontracts import subcontract_invoice_lines

    return subcontract_invoice_lines(seed, plan, order, amount, cycle)


def __progress_lines(seed, plan, order, amount):
    from erpnext.setup.construction_demo.contracts import progress_lines

    return progress_lines(seed, plan, order, amount)


def seed_transactions(seed):
    """Create submitted, linked invoices and example full/partial receipts."""
    end_date = getdate(END_DATE)
    for plan in COMPANIES:
        if not frappe.db.exists("Company", plan.name):
            frappe.throw("Run phase=setup before transactions")
        if not frappe.db.exists("Item", "DEMO-CONSTRUCTION-SERVICE"):
            frappe.throw("Run phase=masters before transactions")

        from erpnext.setup.construction_demo.contracts import ensure_sales_order
        from erpnext.setup.construction_demo.subcontracts import ensure_subcontract
        _ensure_opening_cash(seed, plan)
        frappe.db.commit()
        for index in range(1, scaled(plan.projects, seed.scale) + 1):
            project_label = seed.project_label(plan, index)
            project = frappe.db.get_value(
                "Project", {"project_name": project_label, "company": plan.name}, "name"
            )
            if not project:
                frappe.throw("Run phase=masters first; missing project " + project_label)
            customer_label = seed.customer_label(
                plan, 1 + ((index - 1) % scaled(plan.customers, seed.scale))
            )
            customer = frappe.db.get_value(
                "Customer", {"customer_name": customer_label}, "name"
            )
            supplier_label = seed.supplier_label(
                plan, 1 + ((index - 1) % scaled(plan.suppliers, seed.scale))
            )
            supplier = frappe.db.get_value(
                "Supplier", {"supplier_name": supplier_label}, "name"
            )
            start = add_months(getdate(START_DATE), (index * 7) % 28)
            order = ensure_sales_order(seed, plan, project, customer, index, start)
            subcontract = ensure_subcontract(seed, plan, project, index, start)
            multiplier = {"KRC": 1, "RDC": 10, "MSE": 100000}[plan.abbr]

            for cycle in range(1, billing_cycles(plan, index) + 1):
                posting = add_months(start, (cycle - 1) * 2)
                posting = posting.replace(day=15)
                if posting > end_date:
                    continue
                revenue = (12_000 + index * 125 + cycle * 290) * multiplier
                expense = round(revenue * (0.62 + (index % 5) * 0.035), 2)
                invoice = _ensure_sales_invoice(
                    seed, plan, project, customer, order, index, cycle, posting, revenue
                )
                _ensure_purchase_invoice(
                    seed, plan, project, supplier, subcontract, index, cycle, posting, expense
                )
                # Intentional mixture: full, partial and unpaid receivables.
                if cycle % 3 == 0:
                    _ensure_customer_receipt(
                        seed, plan, invoice, index, cycle,
                        min(add_days(posting, 20), end_date), 0.95
                    )
                elif cycle % 4 == 0:
                    _ensure_customer_receipt(
                        seed, plan, invoice, index, cycle,
                        min(add_days(posting, 25), end_date), 0.5
                    )
            frappe.db.commit()
    seed.warnings.append(
        "Progress invoices are linked to BOQ Sales Order rows; retention is"
        " represented in payment terms. Simulator tax percentages are not law."
    )
