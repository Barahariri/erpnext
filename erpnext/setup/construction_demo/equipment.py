"""Fixed-asset equipment catalogue for the synthetic construction demo.

Assets are intentionally inserted in DRAFT state. ERPNext's Asset submission
posts GL and requires carefully tested opening balances/depreciation schedules;
that is a separate integration milestone, not fabricated accounting.
"""
from datetime import date

import frappe
from frappe.utils import add_months, getdate

from erpnext.setup.construction_demo.config import (
    COMPANIES, EQUIPMENT_TYPES, scaled
)


def _fixed_asset_account(company: str) -> str:
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Fixed Asset", "is_group": 0},
        "name",
    )
    if not account:
        frappe.throw(
            "No leaf Fixed Asset Account for company "
            + company
            + "; configure chart of accounts before creating equipment."
        )
    return account


def seed_equipment(seed) -> None:
    accounts = [
        {"company_name": plan.name, "fixed_asset_account": _fixed_asset_account(plan.name)}
        for plan in COMPANIES
    ]
    category = seed.ensure(
        "Asset Category",
        {"asset_category_name": "DEMO Construction Machinery"},
        {
            "asset_category_name": "DEMO Construction Machinery",
            "non_depreciable_category": 0,
            "accounts": accounts,
        },
    )
    for i, equipment in enumerate(EQUIPMENT_TYPES, start=1):
        item_code = f"DEMO-EQUIPMENT-TYPE-{i:02d}"
        seed.ensure(
            "Item",
            {"item_code": item_code},
            {
                "item_code": item_code,
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
        location = seed.ensure(
            "Location",
            {"location_name": f"DEMO-{plan.abbr}-EQUIPMENT-YARD"},
            {"location_name": f"DEMO-{plan.abbr}-EQUIPMENT-YARD"},
        )
        for i in range(1, scaled(plan.equipment, seed.scale) + 1):
            name = f"DEMO-{plan.abbr}-ASSET-{i:04d}"
            equipment_index = ((i - 1) % len(EQUIPMENT_TYPES)) + 1
            item_code = f"DEMO-EQUIPMENT-TYPE-{equipment_index:02d}"
            purchased = add_months(getdate("2023-11-01"), (i * 3) % 35)
            currency_multiplier = (
                100000 if plan.abbr == "MSE" else 1.0 if plan.abbr == "KRC" else 10.0
            )
            purchase_amount = (2000 + (i % 37) * 950) * currency_multiplier
            seed.ensure(
                "Asset",
                {"asset_name": name, "company": plan.name},
                {
                    "asset_name": name,
                    "item_code": item_code,
                    "asset_category": category,
                    "company": plan.name,
                    "location": location,
                    "cost_center": seed.default_cost_center(plan.name),
                    "asset_type": "Existing Asset",
                    "asset_owner": "Company",
                    "asset_owner_company": plan.name,
                    "purchase_date": purchased,
                    "available_for_use_date": purchased,
                    "calculate_depreciation": 0,
                    "purchase_amount": purchase_amount,
                    "net_purchase_amount": purchase_amount,
                },
            )
        frappe.db.commit()

    seed.warnings.append(
        "Equipment Assets created as drafts only; not yet booked or depreciated."
    )
