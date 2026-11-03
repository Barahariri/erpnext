"""Opt-in Frappe HRMS v16 synthetic payroll and attendance data.

This module is imported only if the 'hrms' app is installed. Individual Salary
Slips are submitted via HRMS's normal validation. A separate balanced Journal
Entry per month records artificial aggregate wage cost; ERPNext does not post
Salary Slip GL by itself when not processed through Payroll Entry.

IMPORTANT: Do not also use Payroll Entry to book the same salary slips.
All names, benefits, salary amounts and taxes are fictional.
"""
from __future__ import annotations

import calendar
from datetime import date

import frappe
from frappe.utils import add_days, add_months, getdate

from erpnext.setup.construction_demo.config import (
    COMPANIES, DESIGNATIONS, START_DATE, scaled
)


def _account(company, field):
    value = frappe.db.get_value("Company", company, field)
    if not value:
        frappe.throw(f"Missing account: {company}.{field}")
    return value


def _payable(seed, plan):
    name = f"DEMO {plan.abbr} Payroll Payable"
    found = frappe.db.get_value(
        "Account", {"account_name": name, "company": plan.name}, "name"
    )
    if found:
        return found
    parent = frappe.db.get_value(
        "Account", {"company": plan.name, "root_type": "Liability", "is_group": 1},
        "name",
    )
    if not parent:
        frappe.throw("Missing liability group for " + plan.name)
    return seed.ensure(
        "Account", {"account_name": name, "company": plan.name},
        {
            "account_name": name, "company": plan.name,
            "parent_account": parent, "root_type": "Liability",
            "is_group": 0,
        },
    )


def _component(seed, plan, title, abbr, formula):
    name = f"DEMO {plan.abbr} {title}"
    return seed.ensure(
        "Salary Component", {"salary_component": name},
        {
            "salary_component": name,
            "salary_component_abbr": f"{plan.abbr}{abbr}",
            "type": "Earning",
            "is_tax_applicable": 0,
            "amount_based_on_formula": 1,
            "formula": formula,
            "accounts": [{
                "company": plan.name,
                "account": _account(plan.name, "default_expense_account"),
            }],
        },
    )


def _setup_payroll(seed, plan):
    payable = _payable(seed, plan)
    basic = _component(seed, plan, "Basic Pay", "BAS", "base")
    housing = _component(seed, plan, "Housing Allowance", "HOU", "base * 0.20")
    structures = {}
    for role in DESIGNATIONS:
        title = f"DEMO {plan.abbr} {role} Monthly"
        if frappe.db.exists("Salary Structure", title):
            seed.existing["Salary Structure"] += 1
        else:
            doc = frappe.get_doc({
                "doctype": "Salary Structure",
                "name": title, "__newname": title,
                "company": plan.name, "is_active": "Yes",
                "payroll_frequency": "Monthly",
                "currency": plan.currency,
                "salary_slip_based_on_timesheet": 0,
                "earnings": [
                    {"salary_component": basic, "amount_based_on_formula": 1, "formula": "base"},
                    {
                        "salary_component": housing,
                        "amount_based_on_formula": 1,
                        "formula": "base * 0.20",
                    },
                ],
            })
            doc.insert(ignore_permissions=True)
            doc.submit()
            seed.created["Salary Structure"] += 1
        structures[role] = title
    return structures, payable


def _salary(plan, index):
    if plan.abbr == "KRC":
        return 350 + index % 19 * 31
    if plan.abbr == "RDC":
        return 2200 + index % 29 * 130
    # Synthetic SYP amounts use one bookkeeping scale throughout the demo;
    # they are NOT the legally denominated historical exchange amounts.
    return 700000 + index % 23 * 100000


def _employee_rows(plan):
    return frappe.db.get_all(
        "Employee",
        filters={
            "company": plan.name,
            "employee_number": ["like", f"DEMO-{plan.abbr}-EMP-%"],
        },
        fields=[
            "name", "employee_number", "date_of_joining",
            "designation", "relieving_date", "status",
        ],
        order_by="employee_number",
    )


def _assign(seed, plan, rows, structures, payable):
    for i, row in enumerate(rows, start=1):
        role = row.designation if row.designation in structures else DESIGNATIONS[i % len(DESIGNATIONS)]
        start = max(getdate(START_DATE), getdate(row.date_of_joining))
        if frappe.db.exists(
            "Salary Structure Assignment",
            {"employee": row.name, "from_date": start, "docstatus": ["!=", 2]},
        ):
            seed.existing["Salary Structure Assignment"] += 1
            continue
        doc = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": row.name,
            "company": plan.name,
            "salary_structure": structures[role],
            "from_date": start,
            "base": _salary(plan, i),
            "currency": plan.currency,
            "payroll_payable_account": payable,
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        seed.created["Salary Structure Assignment"] += 1
    frappe.db.commit()


def _leave(seed, plan, rows):
    leave = seed.ensure(
        "Leave Type", {"leave_type_name": "DEMO Construction Annual Leave"},
        {
            "leave_type_name": "DEMO Construction Annual Leave",
            "max_leaves_allowed": 24,
        }
    )
    for row in rows:
        joining = getdate(row.date_of_joining)
        relieving = getdate(row.relieving_date) if row.relieving_date else None
        for year in (2024, 2025, 2026):
            start = max(joining, date(year, 1, 1))
            end = min(relieving, date(year, 12, 31)) if relieving else date(year, 12, 31)
            if start > end:
                continue
            if frappe.db.exists(
                "Leave Allocation",
                {"employee": row.name, "leave_type": leave, "from_date": start, "to_date": end},
            ):
                seed.existing["Leave Allocation"] += 1
                continue
            doc = frappe.get_doc({
                "doctype": "Leave Allocation",
                "naming_series": "HR-LAL-.YYYY.-",
                "employee": row.name, "company": plan.name,
                "leave_type": leave, "from_date": start, "to_date": end,
                "new_leaves_allocated": 24,
            })
            doc.insert(ignore_permissions=True)
            doc.submit()
            seed.created["Leave Allocation"] += 1
        frappe.db.commit()


def _attendance(seed, plan, rows):
    # Full scale: two representative attendance records per employee/month,
    # deliberately NOT a biometric daily attendance history.
    months = range(36) if seed.scale == "full" else (0, 17, 35)
    for row in rows:
        joined = getdate(row.date_of_joining)
        left = getdate(row.relieving_date) if row.relieving_date else None
        for month in months:
            first = add_months(getdate(START_DATE), month)
            for day in (10, 20):
                stamp = first.replace(day=day)
                if stamp < joined or (left and stamp > left):
                    continue
                if frappe.db.exists(
                    "Attendance", {"employee": row.name, "attendance_date": stamp},
                ):
                    seed.existing["Attendance"] += 1
                    continue
                code = int(row.employee_number[-3:])
                doc = frappe.get_doc({
                    "doctype": "Attendance",
                    "naming_series": "HR-ATT-.YYYY.-",
                    "employee": row.name, "company": plan.name,
                    "attendance_date": stamp,
                    "status": "Absent" if (day == 20 and month % 7 == 0 and code % 13 == 0) else "Present",
                })
                doc.insert(ignore_permissions=True)
                doc.submit()
                seed.created["Attendance"] += 1
        frappe.db.commit()


def _journal(seed, plan, period, rows_total):
    marker = f"DEMO-{plan.abbr}-PAYROLL-{period:%Y-%m}"
    old = frappe.db.get_value(
        "Journal Entry", {"company": plan.name, "user_remark": marker}, "name",
    )
    if old:
        seed.existing["Journal Entry"] += 1
        existing = frappe.get_doc("Journal Entry", old)
        if existing.docstatus == 0:
            existing.submit()
        return
    if rows_total <= 0:
        return
    expense = _account(plan.name, "default_expense_account")
    payable = _payable(seed, plan)
    cash = _account(plan.name, "default_cash_account")
    center = seed.default_cost_center(plan.name)
    # Pay 93% immediately; the remaining 7% becomes payroll payable.
    # This is one balanced 3-line JE, avoiding duplicate dr/cr to payable.
    paid = round(rows_total * 0.93, 2)
    outstanding = round(rows_total - paid, 2)
    doc = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "naming_series": "ACC-JV-.YYYY.-",
        "posting_date": period,
        "company": plan.name,
        "user_remark": marker,
        "accounts": [
            {
                "account": expense, "debit_in_account_currency": rows_total,
                "cost_center": center,
            },
            {
                "account": cash, "credit_in_account_currency": paid,
            },
            {
                "account": payable, "credit_in_account_currency": outstanding,
            },
        ],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    seed.created["Journal Entry"] += 1


def _slips(seed, plan, rows):
    months = range(36) if seed.scale == "full" else (0, 17, 35)
    for month in months:
        first = add_months(getdate(START_DATE), month)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        total = 0.0
        for row in rows:
            joined = getdate(row.date_of_joining)
            relieved = getdate(row.relieving_date) if row.relieving_date else None
            if joined > last or (relieved and relieved < first):
                continue
            old = frappe.db.get_value(
                "Salary Slip",
                {
                    "employee": row.name,
                    "start_date": first,
                    "end_date": last,
                    "docstatus": ["!=", 2],
                },
                "name",
            )
            if old:
                slip = frappe.get_doc("Salary Slip", old)
                seed.existing["Salary Slip"] += 1
            else:
                assignment = frappe.db.get_value(
                    "Salary Structure Assignment",
                    {
                        "employee": row.name,
                        "from_date": ["<=", last],
                        "docstatus": 1,
                    },
                    "salary_structure",
                    order_by="from_date desc",
                )
                if not assignment:
                    frappe.throw(f"No salary assignment for {row.name} at {last}")
                slip = frappe.get_doc({
                    "doctype": "Salary Slip",
                    "employee": row.name,
                    "company": plan.name,
                    "salary_structure": assignment,
                    "salary_slip_based_on_timesheet": 0,
                    "payroll_frequency": "Monthly",
                    "start_date": first, "end_date": last,
                    "posting_date": last,
                    "currency": plan.currency,
                    "exchange_rate": 1,
                })
                slip.insert(ignore_permissions=True)
                seed.created["Salary Slip"] += 1
            if slip.docstatus == 0:
                original = getattr(frappe.flags, "via_payroll_entry", False)
                frappe.flags.via_payroll_entry = True
                try:
                    slip.submit()
                finally:
                    frappe.flags.via_payroll_entry = original
            total += float(slip.net_pay or 0)
        _journal(seed, plan, last, round(total, 2))
        frappe.db.commit()


def seed_hrms(seed):
    if "hrms" not in frappe.get_installed_apps():
        seed.warnings.append("HRMS not installed: payroll, attendance and leave skipped")
        return
    for plan in COMPANIES:
        if not frappe.db.exists("Company", plan.name):
            frappe.throw("Setup must run before HRMS")
        structures, payable = _setup_payroll(seed, plan)
        rows = _employee_rows(plan)
        if not rows:
            frappe.throw("Masters phase required before HRMS")
        _assign(seed, plan, rows, structures, payable)
        _leave(seed, plan, rows)
        _attendance(seed, plan, rows)
        _slips(seed, plan, rows)
    seed.warnings.append(
        "HRMS slips and separate synthetic payroll JE generated; do NOT run "
        "Payroll Entry accrual on these same slips (would double-book wages). "
        "Daily biometric attendance and tax-compliant payroll are not modeled."
    )
