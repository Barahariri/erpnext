"""BOQ-based subcontract procurement with progress billing (DEMO only)."""
from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import add_months, getdate

from erpnext.setup.construction_demo.config import START_DATE, scaled

SUBCONTRACT_WEIGHTS = (
    ("الحفر والتهيئة / Earthworks", "0.35"),
    ("الخرسانة والإنشاء / Concrete Works", "0.45"),
    ("الكهرباء والميكانيك / MEP", "0.20"),
)


def _supplier(seed, plan, index):
    label = seed.supplier_label(
        plan, 1 + ((index - 1) % scaled(plan.suppliers, seed.scale)),
    )
    name = frappe.db.get_value("Supplier", {"supplier_name": label}, "name")
    if not name:
        frappe.throw("Missing demo subcontract supplier " + label)
    return name


def contract_amount(plan, index, start):
    multiplier = {"KRC": 1, "RDC": 10, "MSE": 100000}[plan.abbr]
    subtotal = Decimal("0")
    cutoff = getdate("2026-10-31")
    for cycle in range(1, 9):
        posting = add_months(start, (cycle - 1) * 2).replace(day=15)
        if posting > cutoff:
            continue
        revenue = (12_000 + index * 125 + cycle * 290) * multiplier
        expense = round(revenue * (0.62 + index % 5 * 0.035), 2)
        subtotal += Decimal(str(expense))
    return float(subtotal * Decimal("1.12"))


def ensure_subcontract(seed, plan, project, index, start):
    marker = f"DEMO-{plan.abbr}-SUBCON-{index:03d}"
    existing = frappe.db.get_value(
        "Purchase Order", {"company": plan.name, "order_confirmation_no": marker}, "name"
    )
    if existing:
        seed.existing["Purchase Order"] += 1
        contract = frappe.get_doc("Purchase Order", existing)
        if contract.docstatus == 0:
            contract.submit()
        return contract

    supplier = _supplier(seed, plan, index)
    amount = Decimal(str(contract_amount(plan, index, start)))
    items = []
    for label, weight in SUBCONTRACT_WEIGHTS:
        items.append({
            "item_code": "DEMO-CONSTRUCTION-SERVICE",
            "item_name": "Subcontract Work Package",
            "description": f"DEMO Subcontract BOQ: {label}",
            "qty": 100,
            "uom": "DEMO Percent Point",
            "rate": float(amount * Decimal(weight) / Decimal("100")),
            "schedule_date": add_months(start, 20),
            "project": project,
            "cost_center": seed.default_cost_center(plan.name),
        })
    contract = frappe.get_doc({
        "doctype": "Purchase Order",
        "naming_series": "PUR-ORD-.YYYY.-",
        "company": plan.name, "supplier": supplier,
        "transaction_date": start,
        "schedule_date": add_months(start, 20),
        "order_confirmation_no": marker,
        "order_confirmation_date": start,
        "currency": plan.currency, "conversion_rate": 1,
        "buying_price_list": "Standard Buying",
        "price_list_currency": plan.currency,
        "plc_conversion_rate": 1,
        "project": project,
        "cost_center": seed.default_cost_center(plan.name),
        "items": items,
    })
    from erpnext.setup.construction_demo.taxes import apply_taxes
    apply_taxes(contract, plan, mode="country")
    contract.insert(ignore_permissions=True)
    contract.submit()
    seed.created["Purchase Order"] += 1
    return contract


def subcontract_invoice_lines(seed, plan, order, amount, cycle):
    base = Decimal(str(order.net_total))
    quantity = float(Decimal(str(amount)) / base * Decimal(100))
    lines = []
    for row in order.items:
        lines.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "description": f"{row.description}, certified installment #{cycle}",
            "qty": quantity,
            "uom": "DEMO Percent Point",
            "rate": row.rate,
            "purchase_order": order.name,
            "po_detail": row.name,
            "expense_account": frappe.db.get_value(
                "Company", plan.name, "default_expense_account",
            ),
            "cost_center": seed.default_cost_center(plan.name),
            "project": order.project,
        })
    return lines
