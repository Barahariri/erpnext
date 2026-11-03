"""Read-only post-run audit for the ERPNext construction demo.

Usage:
  bench --site SITE execute erpnext.setup.construction_demo.audit.report

This does NOT modify data. Financial totals are reported in each company's
own currency; there is no fabricated cross-company FX conversion.
"""
from __future__ import annotations

import frappe

from erpnext.setup.construction_demo.config import COMPANIES, SEED_VERSION


def _count(doctype, filters):
    return frappe.db.count(doctype, filters)


def _gl_balance(company):
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(debit), 0) AS debit,
               COALESCE(SUM(credit), 0) AS credit,
               COALESCE(SUM(debit - credit), 0) AS difference
        FROM `tabGL Entry`
        WHERE company = %s AND IFNULL(is_cancelled, 0) = 0
        """,
        (company,),
        as_dict=True,
    )
    return {key: float(result[0][key] or 0) for key in ("debit", "credit", "difference")}


def report() -> dict:
    """Audit values only; safe to run before/after a seed operation."""
    summary = {
        "seed_version": SEED_VERSION,
        "companies": {},
        "errors": [],
        "warnings": [],
        "verification_note": "This is an audit, not a legal or tax compliance certification.",
    }
    has_hrms = "hrms" in frappe.get_installed_apps()
    for plan in COMPANIES:
        if not frappe.db.exists("Company", plan.name):
            summary["errors"].append(f"Missing company: {plan.name}")
            continue
        counts = {
            "employees": _count("Employee", {"company": plan.name, "employee_number": ["like", f"DEMO-{plan.abbr}-EMP-%"]}),
            "projects": _count("Project", {"company": plan.name, "project_name": ["like", f"DEMO-{plan.abbr}-PRJ-%"]}),
            "assets": _count("Asset", {"company": plan.name, "asset_name": ["like", f"DEMO-{plan.abbr}-ASSET-%"]}),
            "sales_orders": _count("Sales Order", {"company": plan.name, "po_no": ["like", f"DEMO-{plan.abbr}-CONTRACT-%"], "docstatus": 1}),
            "sales_invoices": _count("Sales Invoice", {"company": plan.name, "po_no": ["like", f"DEMO-{plan.abbr}-PRJ-%"], "docstatus": 1}),
            "purchase_orders": _count("Purchase Order", {"company": plan.name, "order_confirmation_no": ["like", f"DEMO-{plan.abbr}-STOCK-%"], "docstatus": 1}),
            "receipts": _count("Purchase Receipt", {"company": plan.name, "docstatus": 1}),
            "stock_issues": _count("Stock Entry", {"company": plan.name, "remarks": ["like", "DEMO-STOCK-ISSUE-%"], "docstatus": 1}),
            "payments": _count("Payment Entry", {"company": plan.name, "reference_no": ["like", "DEMO-%"], "docstatus": 1}),
        }
        if has_hrms:
            counts["salary_slips"] = _count(
                "Salary Slip", {"company": plan.name, "docstatus": 1}
            )
            counts["attendance_samples"] = _count("Attendance", {"company": plan.name})
        financial = _gl_balance(plan.name)
        summary["companies"][plan.abbr] = {
            "company": plan.name,
            "currency": plan.currency,
            "counts": counts,
            "gl_balance": financial,
        }
        if abs(financial["difference"]) > 0.05:
            summary["errors"].append(
                f"Unbalanced general ledger for {plan.abbr}: {financial['difference']}"
            )
        for label, required in [
            ("employees", plan.employees),
            ("projects", plan.projects),
            ("assets", plan.equipment),
        ]:
            if counts[label] < required:
                summary["warnings"].append(
                    f"{plan.abbr}: only {counts[label]} of {required} planned {label}; "
                    "may be pilot or a partially completed full run."
                )

    bad_tax = frappe.db.sql(
        """
        SELECT si.company, si.name, tx.rate, tx.description
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Taxes and Charges` tx
          ON tx.parent = si.name AND tx.parenttype = 'Sales Invoice'
        WHERE si.docstatus = 1
          AND si.po_no LIKE 'DEMO-%%'
          AND tx.rate > 0
          AND tx.description NOT LIKE '%%SIMULATED%%'
        LIMIT 15
        """,
        as_dict=True,
    )
    if bad_tax:
        summary["errors"].append(
            "Positive-rate non-simulated taxes found on demo invoices: "
            + ", ".join(row.name for row in bad_tax)
        )
    if not has_hrms:
        summary["warnings"].append(
            "Frappe HRMS app is absent. Payroll and attendance simulation was skipped."
        )
    return summary
