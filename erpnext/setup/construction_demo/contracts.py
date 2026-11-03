"""Construction BOQ / contract simulator using native ERPNext Sales Orders.

A single Sales Order is the signed contract. Its five item rows are the BOQ
work packages. Eight progress certificates are attached as Sales Invoices
against these SAME Sales Order Item records, so billed percentages reconcile.
"""
from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import add_days, add_months, getdate

from erpnext.setup.construction_demo.config import PROJECT_STAGES, START_DATE

BOQ_SPLIT = ("0.07", "0.22", "0.35", "0.25", "0.11")
assert sum(Decimal(x) for x in BOQ_SPLIT) == Decimal("1.00")


def payment_terms(seed):
    # A contractual 5% retention is a delayed receivable, NOT a tax or
    # reduction in recognized revenue. See payment schedule on the invoice.
    due = seed.ensure(
        "Payment Term", {"payment_term_name": "DEMO Progress Payment 95"},
        {"payment_term_name": "DEMO Progress Payment 95"},
    )
    retain = seed.ensure(
        "Payment Term", {"payment_term_name": "DEMO Retention Guarantee 5"},
        {"payment_term_name": "DEMO Retention Guarantee 5"},
    )
    name = "DEMO Construction 95pct + 5pct Retention"
    return seed.ensure(
        "Payment Terms Template", {"template_name": name},
        {
            "template_name": name,
            "terms": [
                {
                    "payment_term": due,
                    "description": "95% payable 45 days after progress invoice.",
                    "invoice_portion": 95,
                    "due_date_based_on": "Day(s) after invoice date",
                    "credit_days": 45,
                },
                {
                    "payment_term": retain,
                    "description": "5% retention payable 365 days later (illustrative).",
                    "invoice_portion": 5,
                    "due_date_based_on": "Day(s) after invoice date",
                    "credit_days": 365,
                },
            ],
        },
    )


def expected_value(plan, index, start):
    cutoff = getdate("2026-10-31")
    multiplier = {"KRC": 1, "RDC": 10, "MSE": 100000}[plan.abbr]
    total = Decimal("0")
    for cycle in range(1, 9):
        posting = add_months(start, (cycle - 1) * 2).replace(day=15)
        if posting > cutoff:
            continue
        total += Decimal(12_000 + index * 125 + cycle * 290) * multiplier
    return float(total * Decimal("1.15"))


def ensure_sales_order(seed, plan, project, customer, index, start):
    marker = f"DEMO-{plan.abbr}-CONTRACT-{index:03d}"
    old = frappe.db.get_value(
        "Sales Order",
        {"company": plan.name, "po_no": marker},
        "name",
    )
    if old:
        seed.existing["Sales Order"] += 1
        doc = frappe.get_doc("Sales Order", old)
        if doc.docstatus == 0:
            doc.submit()
        return doc

    contract_amount = Decimal(str(expected_value(plan, index, start)))
    items = []
    # Contract quantity represents 100 percentage-points per BOQ package.
    for stage, weight in zip(PROJECT_STAGES, BOQ_SPLIT):
        row_amount = contract_amount * Decimal(weight)
        items.append({
            "item_code": "DEMO-CONSTRUCTION-SERVICE",
            "item_name": "Construction Work Package",
            "description": f"DEMO BOQ: {stage} | progress measured in percentage-points",
            "qty": 100,
            "uom": "DEMO Percent Point",
            "rate": float(row_amount / 100),
            "delivery_date": add_months(start, 20),
            "project": project,
            "cost_center": seed.default_cost_center(plan.name),
        })
    from erpnext.setup.construction_demo.taxes import apply_taxes

    doc = frappe.get_doc({
        "doctype": "Sales Order",
        "naming_series": "SAL-ORD-.YYYY.-",
        "order_type": "Sales",
        "company": plan.name,
        "customer": customer,
        "project": project,
        "transaction_date": start,
        "delivery_date": add_months(start, 20),
        "po_no": marker,
        "po_date": start,
        "title": f"DEMO Construction Contract | {project}",
        "currency": plan.currency,
        "conversion_rate": 1,
        "selling_price_list": f"DEMO {plan.abbr} Selling",
        "price_list_currency": plan.currency,
        "plc_conversion_rate": 1,
        "payment_terms_template": payment_terms(seed),
        "cost_center": seed.default_cost_center(plan.name),
        "items": items,
    })
    # Contract itself follows actual-country no-VAT status: simulated tax
    # applies only to selected test invoices, never silently to contracts.
    apply_taxes(doc, plan, mode="country")
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Sales Order"] += 1
    return doc


def progress_lines(seed, plan, sales_order, period_amount):
    """Generate a five-line invoice matched to five contract BOQ rows."""
    amount = Decimal(str(period_amount))
    contract = Decimal(str(sales_order.net_total))
    if contract <= 0:
        frappe.throw("Zero contract total for " + sales_order.name)
    quantity_per_package = amount / contract * Decimal(100)
    lines = []
    for row in sales_order.items:
        lines.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "description": f"{row.description} | DEMO certified progress",
            "qty": float(quantity_per_package),
            "uom": "DEMO Percent Point",
            "rate": row.rate,
            "sales_order": sales_order.name,
            "so_detail": row.name,
            "project": sales_order.project,
            "cost_center": seed.default_cost_center(plan.name),
            "income_account": frappe.db.get_value(
                "Company", plan.name, "default_income_account",
            ),
        })
    return lines
