"""Country-aware illustrative invoice tax treatments for the construction demo.

IMPORTANT: 2026-11-03 verification:
* Kuwait: no enacted VAT regime.
* Qatar: no enacted VAT regime.
* Syria: no general VAT. Selective consumption expenditure fees may apply
  depending on item/service and date; this demo NEVER guesses applicability.

Mode "country" generates documented no-VAT invoices, with 0% informational
tax rows. Mode "simulated" additionally mixes *explicitly fictional* 5% VAT
stress-test invoices. No scenario is a substitute for tax legal advice.
"""
from __future__ import annotations

import frappe

# Keep legal status explicit: a 0% informational row is NOT a zero-rated
# registered supply or an exemption declaration.
TAX_STATUS = {
    "KRC": "Kuwait: no VAT implemented (not a zero-rated supply).",
    "RDC": "Qatar: no VAT implemented (not a zero-rated supply).",
    "MSE": "Syria: no general VAT; selective consumption fees not modeled automatically.",
}
TAX_RATE_TEST = 5.0


def _group_account(company: str, root_type: str):
    candidate = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": root_type, "is_group": 1},
        "name",
    )
    if not candidate:
        frappe.throw(f"No {root_type} parent account in {company}")
    return candidate


def _account(seed, plan, label, root_type):
    full_name = f"DEMO {plan.abbr} {label}"
    existing = frappe.db.get_value(
        "Account", {"company": plan.name, "account_name": full_name}, "name"
    )
    if existing:
        seed.existing["Account"] += 1
        return existing
    return seed.ensure(
        "Account", {"company": plan.name, "account_name": full_name},
        {
            "company": plan.name,
            "account_name": full_name,
            "parent_account": _group_account(plan.name, root_type),
            "is_group": 0,
            "root_type": root_type,
            "account_type": "Tax" if root_type == "Liability" else "",
        },
    )


def _tax_template(seed, plan, doctype, title, account, rate, description):
    existing = frappe.db.get_value(
        doctype, {"title": title, "company": plan.name}, "name"
    )
    if existing:
        seed.existing[doctype] += 1
        return existing
    row = {
        "charge_type": "On Net Total",
        "account_head": account,
        "description": description,
        "rate": rate,
        "included_in_print_rate": 0,
    }
    if doctype == "Purchase Taxes and Charges Template":
        row.update({"category": "Total", "add_deduct_tax": "Add"})
    return seed.ensure(
        doctype, {"title": title, "company": plan.name},
        {
            "title": title,
            "company": plan.name,
            "is_default": 0,
            "taxes": [row],
        },
    )


def setup_taxes(seed):
    for plan in seed.companies:
        out = _account(seed, plan, "Illustrative Sales Tax Output", "Liability")
        inp = _account(seed, plan, "Illustrative Purchase Tax Input", "Asset")
        _tax_template(
            seed, plan, "Sales Taxes and Charges Template",
            f"DEMO {plan.abbr} NO VAT (informational)",
            out, 0,
            TAX_STATUS[plan.abbr] + " DEMO ONLY",
        )
        _tax_template(
            seed, plan, "Purchase Taxes and Charges Template",
            f"DEMO {plan.abbr} NO VAT (informational)",
            inp, 0,
            TAX_STATUS[plan.abbr] + " DEMO ONLY",
        )
        _tax_template(
            seed, plan, "Sales Taxes and Charges Template",
            f"DEMO {plan.abbr} SIMULATED TAX 5% - NOT LAW",
            out, TAX_RATE_TEST,
            "SIMULATED 5% tax for software testing ONLY. NOT APPLICABLE LAW.",
        )
        _tax_template(
            seed, plan, "Purchase Taxes and Charges Template",
            f"DEMO {plan.abbr} SIMULATED TAX 5% - NOT LAW",
            inp, TAX_RATE_TEST,
            "SIMULATED 5% tax for software testing ONLY. NOT APPLICABLE LAW.",
        )
    frappe.db.commit()


def apply_taxes(doc, plan, mode: str = "country", simulated: bool = False):
    """Copy template rows explicitly: Python document inserts do not fire JS."""
    if mode not in ("country", "simulated"):
        frappe.throw("tax_mode must be country or simulated")
    chosen_sim = bool(mode == "simulated" and simulated)
    kind = (
        "Sales Taxes and Charges Template"
        if doc.doctype in ("Sales Invoice", "Sales Order")
        else "Purchase Taxes and Charges Template"
    )
    title = (
        f"DEMO {plan.abbr} SIMULATED TAX 5% - NOT LAW"
        if chosen_sim
        else f"DEMO {plan.abbr} NO VAT (informational)"
    )
    name = frappe.db.get_value(kind, {"company": plan.name, "title": title}, "name")
    if not name:
        frappe.throw(f"Missing demo tax template {title}; run setup phase first")
    template = frappe.get_doc(kind, name)
    doc.taxes_and_charges = template.name
    doc.set("taxes", [])
    for source in template.taxes:
        values = {
            "charge_type": source.charge_type,
            "account_head": source.account_head,
            "description": source.description,
            "rate": source.rate,
            "included_in_print_rate": source.included_in_print_rate,
        }
        if kind == "Purchase Taxes and Charges Template":
            values.update(
                {
                    "category": source.category,
                    "add_deduct_tax": source.add_deduct_tax,
                }
            )
        doc.append("taxes", values)
    return chosen_sim
