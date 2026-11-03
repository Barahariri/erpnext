"""Opt-in, repeatable construction demo generator for ERPNext 16.

Run with:
  bench --site SITE execute erpnext.setup.construction_demo.seed.run
  bench --site SITE execute erpnext.setup.construction_demo.seed.run --kwargs '{"dry_run":0,"scale":"pilot","phase":"masters","confirmation":"GENERATE_CONSTRUCTION_DEMO"}'

Writes require construction_demo_enabled=1 in the *test site's* config.
Do NOT enable this flag on production. This is intentionally not a patch/hook.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import frappe
from frappe.utils import add_months, getdate

from erpnext.setup.construction_demo.config import (
    COMPANIES,
    CONFIRMATION,
    DEPARTMENTS,
    DESIGNATIONS,
    EQUIPMENT_TYPES,
    FIRST_NAMES,
    LAST_NAMES,
    MATERIALS,
    MATERIAL_COUNT,
    ORG_NAMES,
    PROJECT_CATALOG,
    PROJECT_STAGES,
    PROJECT_TYPES,
    SEED_VERSION,
    expected_totals,
    scaled,
)

VALID_PHASES = ("setup", "masters", "assets", "transactions", "procurement", "hrms", "all")


def run(
    dry_run: int = 1,
    scale: str = "pilot",
    phase: str = "all",
    confirmation: str | None = None,
    tax_mode: str = "country",
) -> dict:
    """Bench entry point. Defaults to a read-only, lightweight preview."""
    if scale not in ("pilot", "full"):
        frappe.throw("scale must be pilot or full")
    if phase not in VALID_PHASES:
        frappe.throw("phase must be one of: " + ", ".join(VALID_PHASES))
    if tax_mode not in ("country", "simulated"):
        frappe.throw("tax_mode must be country or simulated")

    result = {
        "seed_version": SEED_VERSION,
        "phase": phase,
        "scale": scale,
        "tax_mode": tax_mode,
        "dry_run": bool(int(dry_run)),
        "expected": expected_totals(scale),
        "period": ["2023-11-01", "2026-10-31"],
        "warnings": [],
    }
    installed = set(frappe.get_installed_apps())
    if "hrms" not in installed:
        result["warnings"].append("HRMS is NOT installed: payroll, attendance and leave transactions are excluded.")
    if int(dry_run):
        return result

    if phase in ("hrms", "all") and "hrms" not in installed:
        frappe.throw(
            "Frappe HRMS version-16 must be installed on the DEMO site "
            "before running phase=all or phase=hrms."
        )
    if confirmation != CONFIRMATION:
        frappe.throw("Explicit demo confirmation is required: " + CONFIRMATION)
    if not frappe.conf.get("construction_demo_enabled"):
        frappe.throw("Site config construction_demo_enabled=1 is required. NEVER use on production.")
    if frappe.conf.get("developer_mode") is None:
        result["warnings"].append("Verify that this is an isolated test site before seeding.")
    if frappe.session.user != "Administrator":
        frappe.throw("Run this offline via bench execute as Administrator")

    seed = ConstructionDemo(scale, tax_mode=tax_mode)
    if phase in ("setup", "all"):
        seed.setup()
    if phase in ("masters", "all"):
        seed.masters()
    if phase in ("assets", "all"):
        seed.assets()
    if phase in ("transactions", "all"):
        from erpnext.setup.construction_demo.transactions import seed_transactions
        from erpnext.setup.construction_demo.equipment_usage import seed_equipment_usage

        seed_transactions(seed)
        seed_equipment_usage(seed)
    if phase in ("procurement", "all"):
        from erpnext.setup.construction_demo.procurement import seed_procurement
        seed_procurement(seed)
    if phase in ("hrms", "all"):
        from erpnext.setup.construction_demo.hrms_seed import seed_hrms
        seed_hrms(seed)
    result["created"] = dict(seed.created)
    result["already_exists"] = dict(seed.existing)
    result["warnings"].extend(seed.warnings)
    return result


class ConstructionDemo:
    def __init__(self, scale: str, tax_mode: str = "country"):
        self.scale = scale
        self.tax_mode = tax_mode
        self.companies = COMPANIES
        self.created = Counter()
        self.existing = Counter()
        self.warnings: list[str] = []

    def ensure(self, doctype: str, filters: dict, fields: dict) -> str:
        """Idempotent by business-key; never update an existing non-demo record."""
        current = frappe.db.exists(doctype, filters)
        if current:
            self.existing[doctype] += 1
            return current
        doc = frappe.get_doc({"doctype": doctype, **fields})
        doc.insert(ignore_permissions=True)
        self.created[doctype] += 1
        return doc.name

    def company_name(self, plan) -> str:
        return plan.name

    def default_cost_center(self, company: str) -> str:
        center = frappe.db.get_value(
            "Cost Center", {"company": company, "is_group": 0}, "name"
        )
        if not center:
            frappe.throw("Missing non-group Cost Center in " + company)
        return center

    @staticmethod
    def regional_site(plan, district: str) -> str:
        """Operational region for each actual project district."""
        if plan.abbr == "KRC":
            return plan.sites[1] if district in ("الأحمدي", "الفحيحيل", "العقيلة") else plan.sites[0]
        if plan.abbr == "RDC":
            return plan.sites[1] if district in ("الريان", "أم صلال", "لوسيل") else plan.sites[0]
        return plan.sites[1] if district in ("عدرا الصناعية", "جرمانا", "صحنايا", "قدسيا") else plan.sites[0]

    def project_cost_center(self, plan, index: int) -> str:
        spec = PROJECT_CATALOG[plan.abbr][index - 1]
        site = self.regional_site(plan, spec.district)
        center = frappe.db.get_value(
            "Cost Center",
            {"company": plan.name, "cost_center_name": f"DEMO {plan.abbr} {site}"},
            "name",
        )
        return center or self.default_cost_center(plan.name)

    def _company(self, plan) -> None:
        if not frappe.db.exists("Currency", plan.currency):
            frappe.throw("Currency not installed: " + plan.currency)
        existing = frappe.db.exists("Company", plan.name)
        if existing:
            details = frappe.db.get_value(
                "Company", existing, ["abbr", "country", "default_currency"], as_dict=True
            )
            if (
                details.abbr != plan.abbr
                or details.country != plan.country
                or details.default_currency != plan.currency
            ):
                frappe.throw("Company already exists with conflicting configuration: " + plan.name)
            self.existing["Company"] += 1
        else:
            self.ensure(
                "Company",
                {"company_name": plan.name},
                {
                    "company_name": plan.name,
                    "abbr": plan.abbr,
                    "country": plan.country,
                    "default_currency": plan.currency,
                    "date_of_establishment": "2018-01-01",
                    "create_chart_of_accounts_based_on": "Standard Template",
                    "chart_of_accounts": "Standard",
                    "valuation_method": "FIFO",
                },
            )
        for side in ("Selling", "Buying"):
            self.ensure(
                "Price List",
                {"price_list_name": f"DEMO {plan.abbr} {side}"},
                {
                    "price_list_name": f"DEMO {plan.abbr} {side}",
                    "currency": plan.currency,
                    "selling": 1 if side == "Selling" else 0,
                    "buying": 1 if side == "Buying" else 0,
                    "enabled": 1,
                },
            )
        parent_center = frappe.db.get_value(
            "Cost Center", {"company": plan.name, "is_group": 1}, "name"
        )
        if not parent_center:
            frappe.throw("Missing root Cost Center for " + plan.name)
        for site in plan.sites:
            self.ensure(
                "Cost Center",
                {"cost_center_name": f"DEMO {plan.abbr} {site}", "company": plan.name},
                {
                    "cost_center_name": f"DEMO {plan.abbr} {site}",
                    "company": plan.name,
                    "parent_cost_center": parent_center,
                    "is_group": 0,
                },
            )
            self.ensure(
                "Warehouse",
                {"warehouse_name": "DEMO " + plan.abbr + " " + site, "company": plan.name},
                {
                    "warehouse_name": "DEMO " + plan.abbr + " " + site,
                    "company": plan.name,
                    "is_group": 0,
                },
            )
        if plan.abbr == "KRC":
            self.ensure(
                "Branch", {"branch": "DEMO KRC Ahmadi"},
                {"branch": "DEMO KRC Ahmadi"},
            )

    def _fiscal_years(self):
        for year in (2023, 2024, 2025, 2026):
            if frappe.db.exists("Fiscal Year", {"year_start_date": ["<=", date(year, 1, 1)], "year_end_date": [">=", date(year, 12, 31)]}):
                self.existing["Fiscal Year"] += 1
                continue
            label = "DEMO-FY-" + str(year)
            self.ensure(
                "Fiscal Year",
                {"year": label},
                {
                    "year": label,
                    "year_start_date": date(year, 1, 1),
                    "year_end_date": date(year, 12, 31),
                },
            )

    def _standard_erpnext_fixtures(self):
        """Initialize standard ERPNext setup records on a blank test site.

        Bench reinstall/install-app do NOT run the Setup Wizard stages.
        Without these fixtures, Company/Item/Customer/Supplier/Stock Entry
        validators fail (Transit warehouse, root Item/Customer/Supplier
        Groups, Territories, Nos UOM, Stock Entry Type and payment modes).
        This is gated by the main site's DEMO opt-in, and never called
        during the read-only preview.
        """
        from erpnext.setup.setup_wizard.operations import install_fixtures

        required = {
            "Item Group": "All Item Groups",
            "Customer Group": "All Customer Groups",
            "Supplier Group": "All Supplier Groups",
            "Territory": "All Territories",
            "Warehouse Type": "Transit",
            "UOM": "Nos",
            "Stock Entry Type": "Material Issue",
            "Mode of Payment": "Cash",
        }
        missing = [
            f"{doctype}: {name}"
            for doctype, name in required.items()
            if not frappe.db.exists(doctype, name)
        ]
        if missing:
            # Native ERPNext v16 fixture installer is duplicate-tolerant.
            # Kuwait is the demo group's primary reporting headquarters.
            install_fixtures.install("Kuwait")
            frappe.db.commit()
            self.warnings.append(
                "Initialized missing native ERPNext Setup Wizard fixtures: "
                + ", ".join(missing)
            )

        # Frappe translations can name the root Item Group differently.
        # Ensure the business-specific parent is selected dynamically.
        if not frappe.db.get_value(
            "Item Group", {"is_group": 1, "parent_item_group": ["is", "not set"]}, "name"
        ):
            frappe.throw("ERPNext Item Group root missing after fixture setup")

        still_missing = [
            f"{doctype}: {name}"
            for doctype, name in required.items()
            if not frappe.db.exists(doctype, name)
        ]
        if still_missing:
            frappe.throw(
                "ERPNext basic setup incomplete after official fixture install: "
                + ", ".join(still_missing)
            )

    def _warehouse_types(self):
        """ERPNext 16 Company.on_update creates a Goods In Transit warehouse.

        On a brand-new site, the optional Stock fixture defining its required
        Warehouse Type may not yet exist. Create it using the DocType API
        before any Company is inserted. Idempotent and DEMO-site-only.
        """
        if frappe.db.exists("Warehouse Type", "Transit"):
            self.existing["Warehouse Type"] += 1
            return
        self.ensure(
            "Warehouse Type",
            {"name": "Transit"},
            {
                "name": "Transit",
                "description": "Required by ERPNext for Goods In Transit warehouses",
            },
        )
        frappe.db.commit()

    def setup(self) -> None:
        self._standard_erpnext_fixtures()
        self._warehouse_types()
        self._fiscal_years()
        for plan in COMPANIES:
            self._company(plan)
            frappe.db.commit()
        from erpnext.setup.construction_demo.taxes import setup_taxes
        from erpnext.setup.construction_demo.custom_fields import install_demo_fields
        from erpnext.setup.construction_demo.print_format import install_print_format
        from erpnext.setup.construction_demo.contracts import payment_terms
        install_demo_fields()
        setup_taxes(self)
        payment_terms(self)
        install_print_format(self)
        frappe.db.commit()

    @staticmethod
    def customer_label(plan, index: int) -> str:
        org = ORG_NAMES[(index - 1) % len(ORG_NAMES)]
        return f"DEMO {plan.abbr} {org} عميل {index:03d}"

    @staticmethod
    def supplier_label(plan, index: int) -> str:
        org = ORG_NAMES[(index + 3) % len(ORG_NAMES)]
        return f"DEMO {plan.abbr} {org} مورد {index:03d}"

    @staticmethod
    def project_label(plan, index: int) -> str:
        projects = PROJECT_CATALOG[plan.abbr]
        if not 1 <= index <= len(projects):
            raise ValueError(f"Unknown {plan.abbr} construction project #{index}")
        specification = projects[index - 1]
        return (
            f"DEMO-{plan.abbr}-PRJ-{index:03d} | "
            f"{specification.name} - {specification.district}"
        )

    def _parties(self, plan):
        for i in range(1, scaled(plan.customers, self.scale) + 1):
            label = self.customer_label(plan, i)
            self.ensure(
                "Customer", {"customer_name": label},
                {"customer_name": label, "customer_type": "Company", "naming_series": "CUST-.YYYY.-"},
            )
        for i in range(1, scaled(plan.suppliers, self.scale) + 1):
            label = self.supplier_label(plan, i)
            self.ensure(
                "Supplier", {"supplier_name": label},
                {"supplier_name": label, "supplier_type": "Company", "naming_series": "SUP-.YYYY.-"},
            )

    def _materials(self):
        from frappe.utils.nestedset import get_root_of

        root_item_group = get_root_of("Item Group")
        if not root_item_group:
            frappe.throw("Missing top-level Item Group: run setup phase first")

        # Work progress is naturally fractional; ERPNext "Nos" rejects
        # decimal percentages when its UOM requires whole numbers.
        self.ensure(
            "UOM", {"uom_name": "DEMO Percent Point"},
            {"uom_name": "DEMO Percent Point", "must_be_whole_number": 0},
        )
        self.ensure(
            "Item Group",
            {"item_group_name": "DEMO Construction Materials"},
            {
                "item_group_name": "DEMO Construction Materials",
                "parent_item_group": root_item_group,
                "is_group": 0,
            },
        )
        self.ensure(
            "Item Group",
            {"item_group_name": "DEMO Construction Services"},
            {
                "item_group_name": "DEMO Construction Services",
                "parent_item_group": root_item_group,
                "is_group": 0,
            },
        )
        self.ensure(
            "Item",
            {"item_code": "DEMO-CONSTRUCTION-SERVICE"},
            {
                "item_code": "DEMO-CONSTRUCTION-SERVICE",
                "item_name": "DEMO Work Progress Certificate Service",
                "item_group": "DEMO Construction Services",
                "stock_uom": "DEMO Percent Point",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "is_purchase_item": 1,
                "description": "Synthetic construction work item for demo invoices.",
            },
        )
        for i in range(1, scaled(MATERIAL_COUNT, self.scale) + 1):
            material = MATERIALS[(i - 1) % len(MATERIALS)]
            code = f"DEMO-MAT-{i:04d}"
            self.ensure(
                "Item",
                {"item_code": code},
                {
                    "item_code": code,
                    "item_name": f"{material} / صنف {i:04d}",
                    "item_group": "DEMO Construction Materials",
                    "stock_uom": "Nos",
                    "is_stock_item": 1,
                    "description": f"DEMO construction material batch {i:04d}; artificial unit rates.",
                },
            )

    def _departments(self, plan):
        for label in DEPARTMENTS:
            full = f"DEMO {plan.abbr} {label}"
            self.ensure(
                "Department",
                {"department_name": full, "company": plan.name},
                {"department_name": full, "company": plan.name},
            )

    def _employees(self, plan):
        for i in range(1, scaled(plan.employees, self.scale) + 1):
            number = f"DEMO-{plan.abbr}-EMP-{i:04d}"
            if frappe.db.exists("Employee", {"employee_number": number}):
                self.existing["Employee"] += 1
                continue
            first = FIRST_NAMES[(i * 3) % len(FIRST_NAMES)]
            last = LAST_NAMES[(i * 7) % len(LAST_NAMES)]
            year = 1980 + (i % 21)
            month = 1 + (i % 12)
            day = 1 + (i % 27)
            department = f"DEMO {plan.abbr} {DEPARTMENTS[i % len(DEPARTMENTS)]}"
            designation = DESIGNATIONS[i % len(DESIGNATIONS)]
            self.ensure(
                "Designation",
                {"designation_name": designation},
                {"designation_name": designation},
            )
            self.ensure(
                "Employee",
                {"employee_number": number},
                {
                    "employee_number": number,
                    "naming_series": "HR-EMP-",
                    "first_name": first,
                    "last_name": last,
                    "company": plan.name,
                    "gender": "Female" if first in ("فاطمة", "سارة", "نور", "ليلى") else "Male",
                    "date_of_birth": date(year, month, day),
                    "date_of_joining": date(2019 + i % 5, month, day),
                    "status": "Active",
                    "relieving_date": None,
                    "branch": "DEMO KRC Ahmadi" if plan.abbr == "KRC" and i % 3 == 0 else None,
                    "department": frappe.db.get_value(
                        "Department",
                        {"department_name": department, "company": plan.name},
                        "name",
                    ),
                    "designation": frappe.db.get_value(
                        "Designation", {"designation_name": designation}, "name"
                    ),
                    "create_user_permission": 0,
                    "create_user_automatically": 0,
                },
            )

    def _projects(self, plan):
        clients = scaled(plan.customers, self.scale)
        for i in range(1, scaled(plan.projects, self.scale) + 1):
            label = self.project_label(plan, i)
            spec = PROJECT_CATALOG[plan.abbr][i - 1]
            customer_name = self.customer_label(plan, 1 + ((i - 1) % clients))
            customer = frappe.db.get_value(
                "Customer", {"customer_name": customer_name}, "name"
            )
            start = add_months(getdate("2023-11-01"), (i * 7) % 28)
            finish = add_months(start, spec.duration_months)
            self.ensure(
                "Warehouse",
                {
                    "warehouse_name": f"DEMO {plan.abbr} PROJECT {i:03d} {spec.district}",
                    "company": plan.name,
                },
                {
                    "warehouse_name": f"DEMO {plan.abbr} PROJECT {i:03d} {spec.district}",
                    "company": plan.name,
                    "is_group": 0,
                },
            )
            from erpnext.setup.construction_demo.contracts import expected_value
            project = self.ensure(
                "Project",
                {"project_name": label, "company": plan.name},
                {
                    "project_name": label,
                    "naming_series": "PROJ-.####",
                    "company": plan.name,
                    "customer": customer,
                    "expected_start_date": start,
                    "expected_end_date": finish,
                    "status": "Completed" if finish < getdate("2026-10-31") else "Open",
                    "estimated_costing": round(expected_value(plan, i, start) * 0.78, 2),
                    "notes": f"DEMO ONLY | {spec.name} | {spec.district} | {spec.scope}",
                    "custom_demo_district": spec.district,
                    "custom_demo_scope": spec.scope,
                    "custom_demo_sector": spec.sector,
                    "cost_center": self.project_cost_center(plan, i),
                    "custom_demo_branch": "DEMO KRC Ahmadi" if (
                        plan.abbr == "KRC" and
                        self.regional_site(plan, spec.district) == "الأحمدي"
                    ) else None,
                },
            )
            for j, stage in enumerate(PROJECT_STAGES, start=1):
                subject = f"DEMO {plan.abbr}-{i:03d} {stage}"
                stage_start = add_months(start, j - 1)
                self.ensure(
                    "Task",
                    {"subject": subject, "project": project},
                    {
                        "subject": subject,
                        "project": project,
                        "company": plan.name,
                        "status": "Completed" if stage_start < getdate("2026-05-01") else "Open",
                        "exp_start_date": stage_start,
                        "exp_end_date": add_months(stage_start, 1),
                        "expected_time": 120 + j * 16,
                    },
                )

    def masters(self) -> None:
        # Require setup first; explicit failure instead of half-created records.
        missing = [plan.name for plan in COMPANIES if not frappe.db.exists("Company", plan.name)]
        if missing:
            frappe.throw("Run phase=setup before masters. Missing: " + ", ".join(missing))
        self._materials()
        frappe.db.commit()
        for plan in COMPANIES:
            self._parties(plan)
            self._departments(plan)
            self._employees(plan)
            self._projects(plan)
            frappe.db.commit()

    def assets(self) -> None:
        """Create funded, submitted synthetic equipment with depreciation and IDs."""
        if not frappe.db.exists("Item Group", {"item_group_name": "DEMO Construction Materials"}):
            frappe.throw("Run phase=masters before assets")
        from erpnext.setup.construction_demo.equipment import seed_equipment
        seed_equipment(self)
        frappe.db.commit()
