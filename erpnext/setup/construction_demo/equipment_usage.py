"""Synthetic equipment fuel expenditure matched to actual demo project Assets.

Each quarterly entry uses two balanced ERPNext Journal Entry Account rows:
project fuel expense debit and company cash credit. Asset code is embedded in
the unique remark; fuel consumption is a *fictional estimate*, not manufacturer
rated consumption or legal tax calculation.
"""
from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import add_months, getdate

from erpnext.setup.construction_demo.config import COMPANIES, END_DATE, scaled


def _fuel_account(seed, company):
    name = f"DEMO {company.abbr} Equipment Fuel Running Cost"
    old = frappe.db.get_value(
        "Account", {"company": company.name, "account_name": name}, "name"
    )
    if old:
        return old
    parent = frappe.db.get_value(
        "Account",
        {"company": company.name, "root_type": "Expense", "is_group": 1},
        "name",
    )
    if not parent:
        frappe.throw("Missing expense account group for " + company.name)
    return seed.ensure(
        "Account",
        {"company": company.name, "account_name": name},
        {
            "company": company.name,
            "account_name": name,
            "parent_account": parent,
            "root_type": "Expense",
            "is_group": 0,
        },
    )


def seed_equipment_usage(seed):
    """Generate <=4 fuel JEs per machine across its project assignment period."""
    for company in COMPANIES:
        expense = _fuel_account(seed, company)
        cash = frappe.db.get_value("Company", company.name, "default_cash_account")
        if not cash:
            frappe.throw("No default Cash Account in " + company.name)
        assets = frappe.db.get_all(
            "Asset",
            filters={
                "company": company.name,
                "docstatus": 1,
                "asset_name": ["like", f"DEMO-{company.abbr}-ASSET-%"],
            },
            fields=[
                "name", "purchase_date", "cost_center", "custom_demo_asset_code",
                "custom_demo_assigned_project", "custom_demo_fuel_lph",
            ],
            order_by="custom_demo_asset_code",
        )
        if not assets:
            frappe.throw("Equipment phase must run before usage phase: " + company.name)
        for machine in assets:
            project = frappe.db.get_value(
                "Project", machine.custom_demo_assigned_project,
                ["company", "expected_start_date", "expected_end_date"], as_dict=True
            )
            if not project or project.company != company.name:
                frappe.throw(f"Equipment {machine.name} has no valid company project")
            start = max(
                getdate(machine.purchase_date),
                getdate(project.expected_start_date),
            )
            end = min(getdate(END_DATE), getdate(project.expected_end_date))
            if start > end:
                continue
            asset_no = int(machine.custom_demo_asset_code.rsplit("-", 1)[-1])
            for cycle in range(4):
                posting = add_months(start, cycle * 3)
                if posting > end:
                    break
                marker = (
                    f"DEMO-{company.abbr}-FUEL-"
                    f"{machine.custom_demo_asset_code}-{posting:%Y-%m}"
                )
                old = frappe.db.get_value(
                    "Journal Entry",
                    {"company": company.name, "user_remark": marker},
                    "name",
                )
                if old:
                    seed.existing["Journal Entry"] += 1
                    jv = frappe.get_doc("Journal Entry", old)
                    if jv.docstatus == 0:
                        jv.submit()
                    continue
                hours = 48 + ((asset_no * 3 + cycle * 17) % 42)
                fuel_litres = hours * float(machine.custom_demo_fuel_lph)
                artificial_unit_price = {
                    "KRC": 0.085, "RDC": 1.1, "MSE": 4500,
                }[company.abbr]
                amount = round(fuel_litres * artificial_unit_price, 2)
                if amount <= 0:
                    continue
                document = frappe.get_doc({
                    "doctype": "Journal Entry",
                    "naming_series": "ACC-JV-.YYYY.-",
                    "voucher_type": "Journal Entry",
                    "posting_date": posting,
                    "company": company.name,
                    "user_remark": marker,
                    "accounts": [
                        {
                            "account": expense,
                            "debit_in_account_currency": amount,
                            "cost_center": machine.cost_center,
                            "project": machine.custom_demo_assigned_project,
                        },
                        {
                            "account": cash,
                            "credit_in_account_currency": amount,
                        },
                    ],
                })
                document.insert(ignore_permissions=True)
                document.submit()
                seed.created["Journal Entry"] += 1
        frappe.db.commit()

    seed.warnings.append(
        "Operating hours and fuel accounting are fictional quarterly sample "
        "expenses; hourly costs do not represent manufacturer fuel ratings."
    )
