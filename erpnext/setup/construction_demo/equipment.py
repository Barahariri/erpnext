"""Synthetic heavy-equipment register and finance simulation (ERPNext 16).

Each piece is a *submitted* Existing Asset with a 60-month straight-line
depreciation schedule, linked location, and a corresponding balanced
acquisition Journal Entry. Funding comes from synthetic equity contribution
or equipment-financing liability (never duplicated with Purchase Invoices).
Past-due depreciation is posted by the real ERPNext asset depreciation engine.

Asset Repair records are demonstrative drafts, without extra financial impact.
"""
from __future__ import annotations

from frappe.utils import add_months, get_last_day, getdate

import frappe

from erpnext.setup.construction_demo.config import (
    COMPANIES, END_DATE, EQUIPMENT_TYPES, scaled
)


def _leaf(company, filters, name):
    result = frappe.db.get_value("Account", {"company": company, **filters}, "name")
    if not result:
        frappe.throw(f"No {name} account configured for {company}")
    return result


def _accounts(seed, plan):
    fixed = _leaf(plan.name, {"account_type": "Fixed Asset", "is_group": 0}, "Fixed Asset")
    accumulated = frappe.db.get_value("Company", plan.name, "accumulated_depreciation_account")
    depreciation = frappe.db.get_value("Company", plan.name, "depreciation_expense_account")
    if not accumulated or not depreciation:
        frappe.throw("Missing asset depreciation accounts for " + plan.name)

    equity = _leaf(plan.name, {"root_type": "Equity", "is_group": 0}, "Equity")
    loan_label = f"DEMO {plan.abbr} Equipment Financing Liability"
    loan = frappe.db.get_value(
        "Account", {"company": plan.name, "account_name": loan_label}, "name",
    )
    if not loan:
        parent = _leaf(plan.name, {"root_type": "Liability", "is_group": 1}, "Liabilities group")
        loan = seed.ensure(
            "Account",
            {"company": plan.name, "account_name": loan_label},
            {
                "company": plan.name,
                "account_name": loan_label,
                "parent_account": parent,
                "root_type": "Liability",
                "is_group": 0,
            },
        )
    return {
        "fixed_asset_account": fixed,
        "accumulated_depreciation_account": accumulated,
        "depreciation_expense_account": depreciation,
        "equity": equity,
        "loan": loan,
    }


def _fund_asset(seed, plan, name, asset, price, purchase_date, accounts, index):
    marker = f"DEMO-{plan.abbr}-ASSET-FUND-{index:04d}"
    old = frappe.db.get_value(
        "Journal Entry", {"company": plan.name, "user_remark": marker}, "name",
    )
    if old:
        seed.existing["Journal Entry"] += 1
        doc = frappe.get_doc("Journal Entry", old)
        if doc.docstatus == 0:
            doc.submit()
        return

    # Fictional capital contribution versus finance lease/credit financing.
    credit = accounts["equity"] if index % 5 in (0, 1) else accounts["loan"]
    doc = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "naming_series": "ACC-JV-.YYYY.-",
        "posting_date": purchase_date,
        "company": plan.name,
        "user_remark": marker,
        "accounts": [
            {
                "account": accounts["fixed_asset_account"],
                "debit_in_account_currency": price,
                "credit_in_account_currency": 0,
                "cost_center": seed.default_cost_center(plan.name),
                "reference_type": "Asset",
                "reference_name": asset.name,
            },
            {
                "account": credit,
                "credit_in_account_currency": price,
                "debit_in_account_currency": 0,
            },
        ],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Journal Entry"] += 1


def _repair(seed, plan, asset, index):
    if index % 13:
        return
    marker = f"DEMO equipment service {plan.abbr}-{index:04d}"
    old = frappe.db.get_value(
        "Asset Repair", {"asset": asset.name, "description": marker}, "name"
    )
    if old:
        seed.existing["Asset Repair"] += 1
        return
    row = frappe.get_doc({
        "doctype": "Asset Repair",
        "naming_series": "ACC-ASR-.YYYY.-",
        "asset": asset.name,
        "company": plan.name,
        "cost_center": seed.default_cost_center(plan.name),
        "failure_date": min(add_months(getdate(asset.purchase_date), 9), getdate(END_DATE)),
        "repair_status": "Pending",
        "repair_cost": round(float(asset.net_purchase_amount or 0) * 0.005, 2),
        "description": marker,
    })
    row.insert(ignore_permissions=True)
    seed.created["Asset Repair"] += 1


def seed_equipment(seed):
    account_data = {p.abbr: _accounts(seed, p) for p in COMPANIES}
    category = seed.ensure(
        "Asset Category",
        {"asset_category_name": "DEMO Construction Machinery"},
        {
            "asset_category_name": "DEMO Construction Machinery",
            "non_depreciable_category": 0,
            "accounts": [
                {"company_name": plan.name, **{
                    name: accounts[name] for name in (
                        "fixed_asset_account",
                        "accumulated_depreciation_account",
                        "depreciation_expense_account",
                    )
                }}
                for plan in COMPANIES
                for accounts in [account_data[plan.abbr]]
            ],
        },
    )
    for i, equipment in enumerate(EQUIPMENT_TYPES, start=1):
        code = f"DEMO-EQUIPMENT-TYPE-{i:02d}"
        seed.ensure(
            "Item", {"item_code": code},
            {
                "item_code": code,
                "item_name": f"DEMO {equipment}",
                "item_group": "DEMO Construction Materials",
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_fixed_asset": 1,
                "is_sales_item": 0,
                "is_purchase_item": 1,
                "asset_category": category,
            },
        )
    frappe.db.commit()

    for plan in COMPANIES:
        accounts = account_data[plan.abbr]
        location = seed.ensure(
            "Location",
            {"location_name": f"DEMO-{plan.abbr}-EQUIPMENT-YARD"},
            {"location_name": f"DEMO-{plan.abbr}-EQUIPMENT-YARD"},
        )
        for i in range(1, scaled(plan.equipment, seed.scale) + 1):
            name = f"DEMO-{plan.abbr}-ASSET-{i:04d}"
            item_code = f"DEMO-EQUIPMENT-TYPE-{((i - 1) % len(EQUIPMENT_TYPES)) + 1:02d}"
            purchased = add_months(getdate("2023-11-01"), (i * 3) % 35)
            multiplier = {"KRC": 1, "RDC": 10, "MSE": 100000}[plan.abbr]
            price = (2000 + i % 37 * 950) * multiplier

            found = frappe.db.get_value(
                "Asset", {"asset_name": name, "company": plan.name}, "name"
            )
            if found:
                asset = frappe.get_doc("Asset", found)
                seed.existing["Asset"] += 1
            else:
                asset = frappe.get_doc({
                    "doctype": "Asset",
                    "naming_series": "ACC-ASS-.YYYY.-",
                    "asset_name": name,
                    "item_code": item_code,
                    "asset_category": category,
                    "asset_type": "Existing Asset",
                    "asset_owner": "Company",
                    "asset_owner_company": plan.name,
                    "company": plan.name,
                    "location": location,
                    "cost_center": seed.default_cost_center(plan.name),
                    "purchase_date": purchased,
                    "available_for_use_date": purchased,
                    "purchase_amount": price,
                    "net_purchase_amount": price,
                    "calculate_depreciation": 1,
                    "finance_books": [{
                        "depreciation_method": "Straight Line",
                        "frequency_of_depreciation": 1,
                        "total_number_of_depreciations": 60,
                        "expected_value_after_useful_life": round(price * 0.1, 2),
                        "depreciation_start_date": get_last_day(add_months(purchased, 1)),
                    }],
                })
                asset.insert(ignore_permissions=True)
                seed.created["Asset"] += 1

            if asset.docstatus == 0:
                asset.submit()
            _fund_asset(seed, plan, name, asset, price, purchased, accounts, i)
            _repair(seed, plan, asset, i)
            if i % 30 == 0:
                frappe.db.commit()
        frappe.db.commit()

    # Use ERPNext's genuine depreciation scheduler; it writes validated
    # depreciation JEs and updates Asset / Asset Depreciation Schedule values.
    # It is expensive on 470 assets and must be load-tested on the pilot site.
    from erpnext.assets.doctype.asset.depreciation import book_depreciation_entries
    book_depreciation_entries(getdate(END_DATE))
    seed.warnings.append(
        "Existing Assets are contributed/financed synthetically, not linked to "
        "vendor equipment Purchase Invoices. Depreciation backfill should be "
        "verified in Asset Depreciation Schedule and GL audit."
    )
