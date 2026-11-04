"""Independent ERPNext v16 multicompany construction sample + numbered chart.

Demo-only fictional records. Run inside erpnext-clean backend container from bench/sites.
Never execute this against the earlier erpnext stack.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import json
import frappe

from erpnext.setup.setup_wizard.operations.install_fixtures import install
from erpnext.accounts.doctype.account.account import update_account_number

SITE = "frontend"
DATA = [
    {
        "company": "Al Muhannadi Contracting", "abbr": "AMQ", "country": "Qatar", "currency": "QAR",
        "clients": ["Lusail Commercial Estates", "Mesaieed Industrial Properties", "Al Wakrah Development Partners"],
        "suppliers": ["Doha Cement Distribution", "Gulf Reinforcement Trading", "Qatar Electrical Supply"],
        "subcontractors": ["Doha Civil Foundations", "Pearl Coast Mechanical Services", "Al Rayyan Steel Fabrication"],
        "projects": [
            ("Lusail Marina Office Tower", "Lusail", 2400000),
            ("Mesaieed Workshop Expansion", "Mesaieed", 1260000),
            ("Al Wakrah Public Parking Facility", "Al Wakrah", 850000),
        ],
        "staff": [
            ("Hamad", "Al Nuaimi", "Project Manager", "Male"),
            ("Saad", "Al Marri", "Civil Engineer", "Male"),
            ("Khalid", "Al Kuwari", "Quantity Surveyor", "Male"),
            ("Fahad", "Al Sulaiti", "Site Supervisor", "Male"),
            ("Mariam", "Al Ansari", "Accountant", "Female"),
            ("Abdulrahman", "Al Mannai", "Procurement Officer", "Male"),
            ("Yousef", "Al Mahmoud", "HSE Officer", "Male"),
            ("Nasser", "Al Thani", "Equipment Operator", "Male"),
            ("Rashid", "Al Hajri", "Foreman", "Male"),
            ("Salem", "Al Kaabi", "Electrician", "Male"),
            ("Omar", "Al Sada", "Storekeeper", "Male"),
            ("Ahmed", "Al Emadi", "Mason", "Male"),
        ],
    },
    {
        "company": "Al Furqan Contracting", "abbr": "AFK", "country": "Kuwait", "currency": "KWD",
        "clients": ["Salmiya Property Holdings", "Shuwaikh Industrial Assets", "Ahmadi Residential Investments"],
        "suppliers": ["Shuwaikh Building Materials", "Gulf Cable Trading House", "Ahmadi Safety Equipment Supply"],
        "subcontractors": ["Kuwait Foundation Specialists", "Bayan Mechanical Contracting", "Jahra Roadworks and Paving"],
        "projects": [
            ("Salmiya Family Residential Complex", "Salmiya", 780000),
            ("Shuwaikh Logistics Distribution Hub", "Shuwaikh", 590000),
            ("Ahmadi Drainage Network Upgrade", "Ahmadi", 360000),
        ],
        "staff": [
            ("Abdullah", "Al Mutairi", "Project Manager", "Male"),
            ("Fahad", "Al Enezi", "Civil Engineer", "Male"),
            ("Bader", "Al Shammari", "Quantity Surveyor", "Male"),
            ("Meshari", "Al Otaibi", "Site Supervisor", "Male"),
            ("Noura", "Al Khaldi", "Accountant", "Female"),
            ("Turki", "Al Rashidi", "Procurement Officer", "Male"),
            ("Mohammad", "Al Dosari", "HSE Officer", "Male"),
            ("Yaqoub", "Al Fadhli", "Equipment Operator", "Male"),
            ("Sulaiman", "Al Ajmi", "Foreman", "Male"),
            ("Jasem", "Al Kandari", "Electrician", "Male"),
            ("Hussain", "Al Qattan", "Storekeeper", "Male"),
            ("Ali", "Al Humaidhi", "Mason", "Male"),
        ],
    },
    {
        "company": "Al Salem Contracting", "abbr": "ALS", "country": "Syria", "currency": "SYP",
        "clients": ["Damascus Residential Properties", "Adra Industrial Facilities", "Qudsaya Community Developments"],
        "suppliers": ["Damascus Cement Suppliers", "Levant Plumbing Materials", "Eastern Electrical Components"],
        "subcontractors": ["Damascus Structural Engineering", "Adra Metal Fabrication", "Barada Mechanical Installations"],
        "projects": [
            ("Mezzeh Apartment Refurbishment", "Damascus", 950000000),
            ("Adra Industrial Storage Warehouse", "Adra", 1560000000),
            ("Qudsaya Water Supply Rehabilitation", "Qudsaya", 620000000),
        ],
        "staff": [
            ("Tarek", "Al Masri", "Project Manager", "Male"),
            ("Khaled", "Al Khatib", "Civil Engineer", "Male"),
            ("Yazan", "Haddad", "Quantity Surveyor", "Male"),
            ("Samer", "Darwish", "Site Supervisor", "Male"),
            ("Lina", "Hassan", "Accountant", "Female"),
            ("Firas", "Hammoud", "Procurement Officer", "Male"),
            ("Majd", "Saleh", "HSE Officer", "Male"),
            ("Rami", "Azzam", "Equipment Operator", "Male"),
            ("Karam", "Shammas", "Foreman", "Male"),
            ("Ziad", "Barakat", "Electrician", "Male"),
            ("Osama", "Dabbagh", "Storekeeper", "Male"),
            ("Maher", "Sabbagh", "Mason", "Male"),
        ],
    },
]

# Account numbers are genuine Account.account_number values, six digits.
# Existing ERPNext standard accounts receive numbers too (in their own ranges).
COA = [
    ("Asset", 119000, "Contract Assets and Work in Progress", [
        ("Unbilled Contract Revenue", "Current Asset"),
        ("Certified Contract Receivables", "Receivable"),
        ("Retention Receivable", "Receivable"),
        ("Project Work in Progress", "Capital Work in Progress"),
        ("Supplier Mobilization Advances", "Current Asset"),
        ("Prepaid Project Expenses", "Current Asset"),
        ("Construction Materials Inventory", "Stock"),
    ]),
    ("Asset", 129000, "Construction Plant and Equipment", [
        ("Heavy Construction Equipment", "Fixed Asset"),
        ("Construction Vehicles", "Fixed Asset"),
        ("Scaffolding and Site Tools", "Fixed Asset"),
        ("Equipment Under Installation", "Capital Work in Progress"),
        ("Accumulated Plant Depreciation", "Accumulated Depreciation"),
    ]),
    ("Liability", 219000, "Construction Contract Liabilities", [
        ("Customer Mobilization Advances", "Current Liability"),
        ("Subcontractor Payables", "Payable"),
        ("Subcontractor Retention Payable", "Payable"),
        ("Accrued Project Costs", "Current Liability"),
        ("Site Payroll Accruals", "Current Liability"),
        ("Performance Bond Fees Payable", "Current Liability"),
    ]),
    ("Income", 419000, "Construction Contract Revenue", [
        ("Progress Billing Revenue", "Income Account"),
        ("Variation Order Revenue", "Income Account"),
        ("Infrastructure Works Revenue", "Income Account"),
        ("Maintenance Contract Revenue", "Income Account"),
        ("Plant Rental Revenue", "Income Account"),
    ]),
    ("Expense", 519000, "Direct Construction Costs", [
        ("Construction Materials Consumed", "Cost of Goods Sold"),
        ("Direct Site Labor", "Direct Expense"),
        ("Subcontractor Works", "Direct Expense"),
        ("Equipment Hire and Fuel", "Direct Expense"),
        ("Equipment Depreciation - Projects", "Depreciation"),
        ("Project Mobilization", "Direct Expense"),
        ("Testing and Inspection", "Direct Expense"),
        ("Site Utilities and Security", "Direct Expense"),
        ("Material Transport and Freight", "Direct Expense"),
        ("Project Permits", "Direct Expense"),
        ("Rework and Waste Disposal", "Direct Expense"),
        ("Safety Equipment and PPE", "Direct Expense"),
    ]),
    ("Expense", 529000, "Construction Site Overheads", [
        ("Project Supervision", "Indirect Expense"),
        ("Site Office Expenses", "Indirect Expense"),
        ("Construction Site Insurance", "Indirect Expense"),
        ("Engineering and Surveying", "Indirect Expense"),
        ("Warranty and Defects Expense", "Indirect Expense"),
        ("Tendering and Estimation", "Indirect Expense"),
    ]),
    ("Expense", 539000, "Corporate Overheads", [
        ("Administrative Salaries", "Indirect Expense"),
        ("Office Rent and Utilities", "Indirect Expense"),
        ("IT Systems and Software", "Indirect Expense"),
        ("Legal and Professional Fees", "Indirect Expense"),
        ("Bank Guarantee Fees", "Indirect Expense"),
        ("Business Development", "Indirect Expense"),
    ]),
]

MATERIALS = [
    ("CEM-050", "Portland Cement Bag 50 kg"),
    ("RBR-012", "Deformed Reinforcing Bar 12 mm"),
    ("RBR-016", "Deformed Reinforcing Bar 16 mm"),
    ("BLK-020", "Hollow Concrete Block 20 cm"),
    ("CAB-025", "Copper Power Cable 2.5 mm"),
    ("PIP-110", "PVC Drainage Pipe 110 mm"),
    ("PIP-050", "PPR Water Pipe 50 mm"),
    ("PPE-001", "Industrial Safety Helmet"),
    ("PPE-002", "Protective Safety Vest"),
    ("WIR-001", "Galvanized Binding Wire Roll"),
    ("FST-010", "Anchor Bolt M10"),
    ("INS-050", "Thermal Insulation Board 50 mm"),
    ("PNT-010", "Exterior Weatherproof Coating 10 L"),
    ("TIL-060", "Porcelain Floor Tile 60 by 60 cm"),
    ("ELE-016", "Industrial Circuit Breaker 16 A"),
    ("PLB-002", "Brass Ball Valve 2 inch"),
    ("SCA-001", "Steel Scaffold Coupler"),
    ("WOD-018", "Formwork Plywood Sheet 18 mm"),
]
SERVICES = [
    ("SRV-PROGRESS", "Construction Progress Certification"),
    ("SRV-SUBCON", "Specialist Subcontracting Works"),
    ("SRV-MEP", "Mechanical and Electrical Installation"),
    ("SRV-DESIGN", "Engineering Supervision Services"),
]

CREATED = Counter()
EXISTING = Counter()


def ensure(doctype, keys, values):
    old = frappe.db.get_value(doctype, keys, "name")
    if old:
        EXISTING[doctype] += 1
        return old
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert(ignore_permissions=True)
    CREATED[doctype] += 1
    return doc.name


def verify_site():
    apps = set(frappe.get_installed_apps())
    if "erpnext" not in apps:
        raise RuntimeError("ERPNext is not installed in clean site")
    expected_url = "https://newerp.holotechnology.net"
    if str(frappe.conf.get("host_name") or "").rstrip("/") != expected_url:
        raise RuntimeError("SAFETY STOP: site host_name is not " + expected_url)
    allowed = {p["company"] for p in DATA}
    other = set(frappe.get_all("Company", pluck="name")) - allowed
    if other:
        raise RuntimeError("Unexpected company in clean site, STOP: " + repr(other))


def fixtures():
    if not frappe.db.exists("Warehouse Type", "Transit") or not frappe.db.exists("Item Group", "All Item Groups"):
        install("Kuwait")
        frappe.db.commit()
    for gender in ("Male", "Female"):
        ensure("Gender", {"gender": gender}, {"gender": gender})
    if not frappe.db.exists("Fiscal Year", "2026"):
        ensure("Fiscal Year", {"year": "2026"}, {
            "year": "2026", "year_start_date": "2026-01-01", "year_end_date": "2026-12-31",
        })
    frappe.db.commit()


def company_setup(d):
    country = d["country"]
    if not frappe.db.exists("Country", country):
        if country == "Syria" and frappe.db.exists("Country", "Syrian Arab Republic"):
            country = "Syrian Arab Republic"
        else:
            raise RuntimeError("Country not found: " + country)
    if not frappe.db.exists("Currency", d["currency"]):
        raise RuntimeError("Currency not found: " + d["currency"])
    name = ensure("Company", {"name": d["company"]}, {
        "company_name": d["company"], "abbr": d["abbr"],
        "country": country, "default_currency": d["currency"],
        "create_chart_of_accounts_based_on": "Standard Template", "chart_of_accounts": "Standard",
        "enable_perpetual_inventory": 1,
    })
    c = frappe.get_doc("Company", name)
    if c.abbr != d["abbr"] or c.default_currency != d["currency"]:
        raise RuntimeError("Company abbreviation or currency conflict: " + name)
    frappe.db.commit()
    return name


def number_accounts(d):
    """Number the actual Account.account_number field without renaming Account IDs.

    This isolated demo has no GL entries at this stage. The official account
    renaming API scans/updates references throughout Frappe and can take hours
    when called once for every account. No renamed Account ID is needed to store
    a valid Account Number. Keep existing Link targets stable and set the field
    directly with validation and an audit. This is NOT for production renumbering.
    """
    company = d["company"]
    expected = {v["company"] for v in DATA}
    if company not in expected:
        raise RuntimeError("Unexpected company in chart numbering: " + company)

    roots = {"Asset": 100000, "Liability": 200000, "Equity": 300000,
             "Income": 400000, "Expense": 500000}
    reserved = {g for _, g, _, _ in COA}
    reserved.update(g + i for _, g, _, leaves in COA
                    for i in range(1, len(leaves) + 1))

    docs = frappe.get_all(
        "Account",
        filters={"company": company},
        fields=["name", "account_name", "account_number", "root_type",
                "parent_account", "is_group"],
        order_by="lft asc",
    )
    if not docs:
        raise RuntimeError("Missing standard chart of accounts for " + company)

    # Validate the entire existing numbering *before* touching anything.
    taken = set()
    unnumbered = []
    for row in docs:
        raw = str(row.account_number or "").strip()
        if not raw:
            unnumbered.append(row)
            continue
        if len(raw) != 6 or not raw.isdigit():
            raise RuntimeError(f"{company}: invalid existing Account Number {raw}: {row.name}")
        n = int(raw)
        base = roots.get(row.root_type)
        if base is None or not base <= n < base + 100000:
            raise RuntimeError(f"{company}: wrong numbering family {raw}: {row.name}")
        if n in taken:
            raise RuntimeError(f"{company}: duplicate Account Number {raw}")
        taken.add(n)

    if frappe.db.count("GL Entry", {"company": company, "is_cancelled": 0}):
        if unnumbered:
            raise RuntimeError(
                f"{company}: {len(unnumbered)} unnumbered accounts with posted GL; "
                "manual accounting review required"
            )
        return

    for root_type, base in roots.items():
        group = [r for r in docs if r.root_type == root_type]
        if not group or len([r for r in group if not r.parent_account]) != 1:
            raise RuntimeError(f"{company}: invalid or missing {root_type} account tree")

    changes = 0
    for root_type, base in roots.items():
        group = [r for r in docs if r.root_type == root_type]
        for index, row in enumerate(group):
            if str(row.account_number or "").strip():
                continue
            number = base if not row.parent_account else base + 100 + index * 10
            # On interrupted/resumed runs some numbers may have been assigned.
            # Never overwrite existing Account Numbers or reserved contractor slots.
            while number in taken or number in reserved:
                number += 1
            if number >= base + 19000:
                raise RuntimeError(f"{company}: standard number range exhausted ({root_type})")
            # Account Number is a real ERPNext field. Keeping Account.name
            # unchanged also preserves all existing Account Links.
            frappe.db.set_value("Account", row.name, "account_number",
                                str(number), update_modified=False)
            taken.add(number)
            changes += 1
    frappe.db.commit()
    remaining = frappe.db.count("Account", {
        "company": company, "account_number": ["in", ["", None]]
    })
    if remaining:
        raise RuntimeError(f"{company}: {remaining} Account Numbers still missing")
    print(f"NUMBERED: {company} total={len(docs)} newly_numbered={changes}", flush=True)


def root_account(company, root_type):
    rows = frappe.get_all("Account", filters={"company": company, "root_type": root_type, "is_group": 1},
                          fields=["name", "parent_account"], order_by="lft asc")
    for r in rows:
        if not r.parent_account:
            return r.name
    raise RuntimeError("Account root missing: " + company + "/" + root_type)


def construction_coa(d):
    company = d["company"]
    for root_type, group_no, group_name, leaves in COA:
        root = root_account(company, root_type)
        parent = ensure("Account", {"company": company, "account_name": group_name}, {
            "company": company, "account_name": group_name, "account_number": str(group_no),
            "parent_account": root, "is_group": 1,
        })
        p = frappe.get_doc("Account", parent)
        if not p.is_group or p.parent_account != root or str(p.account_number) != str(group_no):
            raise RuntimeError("Account group conflict: " + company + "/" + group_name)
        for idx, (name, kind) in enumerate(leaves, start=1):
            num = str(group_no + idx)
            acc = ensure("Account", {"company": company, "account_name": name}, {
                "company": company, "account_name": name, "account_number": num,
                "parent_account": parent, "is_group": 0, "account_type": kind,
            })
            a = frappe.get_doc("Account", acc)
            if a.parent_account != parent or a.is_group or str(a.account_number) != num or a.account_type != kind:
                raise RuntimeError("Account ledger conflict: " + company + "/" + name)
    frappe.db.commit()


def master_groups():
    supplier_root = next((x.name for x in frappe.get_all("Supplier Group", fields=["name", "parent_supplier_group", "is_group"]) if not x.parent_supplier_group and x.is_group), None)
    territory_root = next((x.name for x in frappe.get_all("Territory", fields=["name", "parent_territory", "is_group"]) if not x.parent_territory and x.is_group), None)
    customers = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    if not all((supplier_root, territory_root, customers)):
        raise RuntimeError("Standard master groups not found; fixtures incomplete")
    ensure("Supplier Group", {"supplier_group_name": "Construction Subcontractors"}, {
        "supplier_group_name": "Construction Subcontractors", "is_group": 0, "parent_supplier_group": supplier_root,
    })
    ensure("Supplier Group", {"supplier_group_name": "Construction Material Suppliers"}, {
        "supplier_group_name": "Construction Material Suppliers", "is_group": 0, "parent_supplier_group": supplier_root,
    })
    for name in ("Qatar", "Kuwait", "Syria"):
        ensure("Territory", {"territory_name": name}, {
            "territory_name": name, "is_group": 0, "parent_territory": territory_root,
        })
    for code, name in MATERIALS:
        ensure("Item", {"item_code": code}, {
            "item_code": code, "item_name": name, "item_group": "Raw Material",
            "stock_uom": "Nos", "is_stock_item": 1, "is_sales_item": 0, "is_purchase_item": 1,
        })
    for code, name in SERVICES:
        ensure("Item", {"item_code": code}, {
            "item_code": code, "item_name": name, "item_group": "Services",
            "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 1,
        })
    frappe.db.commit()


def setup_company_price_lists(d):
    """Create matching-currency lists required by ERPNext v16 Sales Order/Invoice."""
    for side in ("Selling", "Buying"):
        title = f"DEMO {d['abbr']} {side}"
        fields = {
            "price_list_name": title, "currency": d["currency"],
            "selling": int(side == "Selling"), "buying": int(side == "Buying"),
            "enabled": 1,
        }
        list_id = ensure("Price List", {"price_list_name": title}, fields)
        doc = frappe.get_doc("Price List", list_id)
        if (doc.currency != d["currency"]
                or int(doc.selling or 0) != fields["selling"]
                or int(doc.buying or 0) != fields["buying"]):
            raise RuntimeError("Conflicting demo price list: " + title)


def company_masters(d):
    company = d["company"]
    setup_company_price_lists(d)
    for customer in d["clients"]:
        ensure("Customer", {"customer_name": customer}, {
            "customer_name": customer, "customer_type": "Company", "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            "territory": d["country"],
        })
    for vendor in d["suppliers"]:
        ensure("Supplier", {"supplier_name": vendor}, {
            "supplier_name": vendor, "supplier_type": "Company", "supplier_group": "Construction Material Suppliers",
        })
    for vendor in d["subcontractors"]:
        ensure("Supplier", {"supplier_name": vendor}, {
            "supplier_name": vendor, "supplier_type": "Company", "supplier_group": "Construction Subcontractors",
        })
    centers = frappe.get_all("Cost Center", filters={"company": company, "is_group": 1},
                             fields=["name", "parent_cost_center"], order_by="lft asc")
    cost_root = next((x.name for x in centers if not x.parent_cost_center), None)
    if not cost_root:
        raise RuntimeError("Missing company Cost Center root: " + company)
    for i, (project, district, amount) in enumerate(d["projects"]):
        client = frappe.db.get_value("Customer", {"customer_name": d["clients"][i]}, "name")
        project_cc = ensure("Cost Center", {"cost_center_name": project, "company": company}, {
            "cost_center_name": project, "company": company, "is_group": 0,
            "parent_cost_center": cost_root,
        })
        project_id = ensure("Project", {"company": company, "project_name": project}, {
            "project_name": project, "company": company, "customer": client,
            "naming_series": "PROJ-.####", "status": "Open", "expected_start_date": "2026-01-12", "expected_end_date": "2027-06-30",
            "estimated_costing": round(amount * .77, 2), "cost_center": project_cc,
            "notes": f"Fictional construction sample. Site: {district}. Contract estimate: {amount:,.0f} {d['currency']}.",
        })
        for stage in ("Site Survey", "Mobilization", "Civil and Structural Works", "Quality Inspection", "Project Handover"):
            subject = f"{project} - {stage}"
            ensure("Task", {"subject": subject, "project": project_id}, {
                "subject": subject, "project": project_id, "company": company,
                "status": "Open", "exp_start_date": "2026-01-12", "exp_end_date": "2027-05-20",
            })
        # One clean company/project warehouse, not mixed into project names.
        ensure("Warehouse", {"company": company, "warehouse_name": f"{district} Project Store"}, {
            "warehouse_name": f"{district} Project Store", "company": company, "is_group": 0,
            "parent_warehouse": frappe.db.get_value("Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ["is", "not set"]}, "name"),
        })
    for i, (first, last, role, gender) in enumerate(d["staff"], start=1):
        ensure("Designation", {"designation_name": role}, {"designation_name": role})
        ensure("Employee", {"employee_number": f"{d['abbr']}-EMP-{i:03d}"}, {
            "employee_number": f"{d['abbr']}-EMP-{i:03d}", "naming_series": "HR-EMP-",
            "first_name": first, "last_name": last, "designation": role,
            "gender": gender, "company": company,
            "date_of_birth": date(1982 + (i % 15), (i % 12) + 1, min(i + 1, 27)),
            "date_of_joining": date(2022 + (i % 4), (i % 12) + 1, 1),
            "status": "Active", "create_user_permission": 0,
            "create_user_automatically": 0,
        })
    frappe.db.commit()
    print(f"MASTERS: {d['abbr']} projects={len(d['projects'])} staff={len(d['staff'])} suppliers={len(d['suppliers'])+len(d['subcontractors'])}", flush=True)


def transaction_samples(d):
    """Real submitted orders, progress invoices, and material purchase orders.

    Stops at the first ERPNext validation error; prior company/project commits
    are retained. Reruns use distinct business reference keys to avoid duplicates.
    """
    c = d["company"]
    project_income = frappe.db.get_value("Account", {"company": c, "account_name": "Progress Billing Revenue"}, "name")
    for i, (project_title, district, budget) in enumerate(d["projects"], start=1):
        prj = frappe.db.get_value("Project", {"company": c, "project_name": project_title}, "name")
        client = frappe.db.get_value("Customer", {"customer_name": d["clients"][i-1]}, "name")
        code = f"{d['abbr']}-CONTRACT-{i:03d}"
        existing_so = frappe.db.get_value("Sales Order", {"company": c, "po_no": code}, "name")
        if existing_so:
            order = frappe.get_doc("Sales Order", existing_so)
        else:
            order = frappe.get_doc({
                "doctype": "Sales Order", "company": c, "customer": client,
                "transaction_date": "2026-06-01", "delivery_date": "2027-05-31",
                "po_no": code, "currency": d["currency"], "conversion_rate": 1,
                "selling_price_list": f"DEMO {d['abbr']} Selling",
                "price_list_currency": d["currency"], "plc_conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "items": [{
                    "item_code": "SRV-PROGRESS", "qty": 4, "rate": round(budget / 4, 2),
                    "delivery_date": "2027-05-31", "project": prj,
                }],
            })
            order.insert(ignore_permissions=True)
            CREATED["Sales Order"] += 1
        if order.docstatus == 0:
            order.submit()
        inv_marker = f"{d['abbr']}-BILL-{i:03d}"
        si_existing = frappe.db.get_value("Sales Invoice", {"company": c, "po_no": inv_marker}, "name")
        if si_existing:
            si = frappe.get_doc("Sales Invoice", si_existing)
            if si.docstatus == 0:
                si.submit()
        else:
            si = frappe.get_doc({
                "doctype": "Sales Invoice", "company": c, "customer": client,
                "posting_date": "2026-08-31", "due_date": "2026-09-30",
                "currency": d["currency"], "conversion_rate": 1,
                "selling_price_list": f"DEMO {d['abbr']} Selling",
                "price_list_currency": d["currency"], "plc_conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "debit_to": frappe.db.get_value(
                    "Account", {"company": c, "account_name": "Certified Contract Receivables", "is_group": 0}, "name"),
                "cost_center": frappe.db.get_value("Project", prj, "cost_center"),
                "po_no": inv_marker, "project": prj,
                "items": [{
                    "item_code": "SRV-PROGRESS", "qty": 1,
                    "rate": round(budget / 4, 2), "income_account": project_income,
                    "project": prj, "cost_center": frappe.db.get_value("Project", prj, "cost_center"),
                    "sales_order": order.name,
                    "so_detail": order.items[0].name,
                }],
            })
            si.insert(ignore_permissions=True)
            si.submit()
            CREATED["Sales Invoice"] += 1
        po_marker = f"{d['abbr']}-MATERIAL-{i:03d}"
        existing_po = frappe.db.get_value("Purchase Order", {"company": c, "order_confirmation_no": po_marker}, "name")
        if existing_po:
            po = frappe.get_doc("Purchase Order", existing_po)
            if po.docstatus == 0:
                po.submit()
        else:
            supplier = frappe.db.get_value("Supplier", {"supplier_name": d["suppliers"][i-1]}, "name")
            item_code = MATERIALS[(i-1) % len(MATERIALS)][0]
            po = frappe.get_doc({
                "doctype": "Purchase Order", "company": c, "supplier": supplier,
                "transaction_date": "2026-07-01", "schedule_date": "2026-08-01",
                "order_confirmation_no": po_marker,
                "currency": d["currency"], "conversion_rate": 1,
                "buying_price_list": f"DEMO {d['abbr']} Buying",
                "price_list_currency": d["currency"], "plc_conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "items": [{"item_code": item_code, "qty": 30 + i * 10,
                           "rate": round(budget / 2200, 2), "schedule_date": "2026-08-01", "project": prj}],
            })
            po.insert(ignore_permissions=True)
            po.submit()
            CREATED["Purchase Order"] += 1
        sub_marker = f"{d['abbr']}-SUBCON-{i:03d}"
        existing_sub = frappe.db.get_value("Purchase Order", {"company": c, "order_confirmation_no": sub_marker}, "name")
        if existing_sub:
            sub_po = frappe.get_doc("Purchase Order", existing_sub)
            if sub_po.docstatus == 0:
                sub_po.submit()
        else:
            sub_supplier = frappe.db.get_value("Supplier", {"supplier_name": d["subcontractors"][i-1]}, "name")
            sub_po = frappe.get_doc({
                "doctype": "Purchase Order", "company": c, "supplier": sub_supplier,
                "transaction_date": "2026-07-01", "schedule_date": "2026-09-15",
                "order_confirmation_no": sub_marker,
                "currency": d["currency"], "conversion_rate": 1,
                "buying_price_list": f"DEMO {d['abbr']} Buying",
                "price_list_currency": d["currency"], "plc_conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "items": [{"item_code": "SRV-SUBCON", "qty": 1,
                           "rate": round(budget * .20, 2), "schedule_date": "2026-09-15", "project": prj}],
            })
            sub_po.insert(ignore_permissions=True)
            sub_po.submit()
            CREATED["Purchase Order"] += 1
        frappe.db.commit()
        print(f"TRANSACTION: {d['abbr']} project={i} submitted sales order, invoice and two purchase orders", flush=True)


def audit():
    result = {"site": SITE, "companies": {}, "errors": []}
    bases = {"Asset": 100000, "Liability": 200000, "Equity": 300000, "Income": 400000, "Expense": 500000}
    for d in DATA:
        c = d["company"]
        if not frappe.db.exists("Company", c):
            result["errors"].append(f"Missing company {c}")
            continue
        accs = frappe.get_all("Account", filters={"company": c},
                             fields=["name", "account_number", "root_type", "is_group", "parent_account"])
        nums = [str(a.account_number or "").strip() for a in accs]
        if any(not x or len(x) != 6 or not x.isdigit() for x in nums):
            result["errors"].append(f"{c}: unnumbered or non-six-digit chart accounts")
        if len(nums) != len(set(nums)):
            result["errors"].append(f"{c}: duplicate Account Numbers")
        for a in accs:
            if a.account_number and a.root_type in bases and int(a.account_number)//100000 != bases[a.root_type]//100000:
                result["errors"].append(f"{c}: wrong account numbering family: {a.name}")
            if a.parent_account:
                pc = frappe.db.get_value("Account", a.parent_account, "company")
                if pc != c:
                    result["errors"].append(f"{c}: cross-company account parent: {a.name}")
        result["companies"][d["abbr"]] = {
            "company": c,
            "currency": frappe.db.get_value("Company", c, "default_currency"),
            "accounts": len(accs),
            "numbered": len([n for n in nums if n]),
            "projects": frappe.db.count("Project", {"company": c}),
            "employees": frappe.db.count("Employee", {"company": c}),
            "customers": len(d["clients"]),
            "suppliers_expected": len(d["suppliers"]) + len(d["subcontractors"]),
            "sales_orders": frappe.db.count("Sales Order", {"company": c, "docstatus": 1}),
            "sales_invoices": frappe.db.count("Sales Invoice", {"company": c, "docstatus": 1}),
            "purchase_orders": frappe.db.count("Purchase Order", {"company": c, "docstatus": 1}),
        }
        if frappe.db.count("Project", {"company": c}) < 3:
            result["errors"].append(f"{c}: missing projects")
        if frappe.db.count("Employee", {"company": c}) < 12:
            result["errors"].append(f"{c}: missing employees")
        for doctype, expected in (("Sales Order", 3), ("Sales Invoice", 3), ("Purchase Order", 6)):
            if frappe.db.count(doctype, {"company": c, "docstatus": 1}) < expected:
                result["errors"].append(f"{c}: missing submitted {doctype} samples")
    return result


# Fleet Management extension for ERPNext 16 + Frappe HRMS 16.
# Existing Vehicle master lives in ERPNext; Vehicle Log lives in HRMS.
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FLEET_CATALOG = {
    "AMQ": [
        ("Toyota", "Hilux", "Pickup", "Diesel", 82000, 118000, "Lusail", 4),
        ("Isuzu", "NPR", "Light Truck", "Diesel", 108000, 195000, "Mesaieed", 6),
        ("Volvo", "FMX 420", "Dump Truck", "Diesel", 145000, 710000, "Al Wakrah", 10),
        ("Mercedes-Benz", "Actros 3340", "Heavy Truck", "Diesel", 127000, 780000, "Lusail", 10),
    ],
    "AFK": [
        ("Toyota", "Land Cruiser 79", "Pickup", "Diesel", 76500, 17600, "Salmiya", 4),
        ("Mitsubishi Fuso", "Canter", "Light Truck", "Diesel", 119000, 11200, "Shuwaikh", 6),
        ("Isuzu", "Giga", "Dump Truck", "Diesel", 139000, 29400, "Ahmadi", 10),
        ("Hino", "500 Series", "Concrete Mixer", "Diesel", 93000, 33200, "Salmiya", 10),
    ],
    "ALS": [
        ("Isuzu", "D-Max", "Pickup", "Diesel", 84000, 420000000, "Damascus", 4),
        ("Iveco", "Daily", "Service Van", "Diesel", 111000, 360000000, "Adra", 4),
        ("Mercedes-Benz", "Arocs", "Dump Truck", "Diesel", 157000, 1600000000, "Qudsaya", 10),
        ("Volvo", "FMX 420", "Heavy Truck", "Diesel", 136000, 1480000000, "Damascus", 10),
    ],
}

FLEET_DRIVERS = {
    "AMQ": [("Jaber", "Al Suwaidi"), ("Abdullah", "Al Mansoori"), ("Ibrahim", "Al Kubaisi")],
    "AFK": [("Nasser", "Al Sulaiman"), ("Khalaf", "Al Ajmi"), ("Salem", "Al Mutairi")],
    "ALS": [("Basel", "Saad"), ("Tamer", "Mansour"), ("Amjad", "Al Ali")],
}

FLEET_FUEL_SUPPLIERS = {
    "AMQ": "Doha Fuel and Lubricants",
    "AFK": "Kuwait Fleet Fuel Services",
    "ALS": "Damascus Lubricants Distribution",
}

FLEET_SERVICE_COST = {
    "AMQ": 450.0, "AFK": 45.0, "ALS": 1850000.0,
}
FLEET_FUEL_PRICE = {
    "AMQ": 2.10, "AFK": .115, "ALS": 11500.0,
}

FLEET_CATEGORIES = [
    ("Engine Oil Change", "Change", "Mileage"),
    ("Brake System Inspection", "Inspection", "Quarterly"),
    ("Tyre Rotation", "Service", "Mileage"),
    ("Air Filter Replacement", "Change", "Mileage"),
    ("Safety Inspection", "Inspection", "Monthly"),
    ("Hydraulic System Inspection", "Inspection", "Half Yearly"),
]


def verify_fleet_dependencies():
    if "hrms" not in set(frappe.get_installed_apps()):
        raise RuntimeError("HRMS is not installed. Install hrms ONLY on erpnext-clean site frontend first.")
    for name in ("Vehicle", "Vehicle Log", "Vehicle Service Item", "Employee", "Project"):
        if not frappe.db.exists("DocType", name):
            raise RuntimeError("Fleet dependency missing: " + name)
    if not frappe.db.exists("UOM", "Litre"):
        ensure("UOM", {"uom_name": "Litre"}, {"uom_name": "Litre"})


def setup_fleet_fields():
    """Extend native forms; do not replace or overwrite ERPNext/HRMS DocTypes."""
    custom_fields = {
        "Vehicle": [
            {"fieldname": "custom_fleet_category", "label": "Fleet Category", "fieldtype": "Select",
             "options": "\nPickup\nLight Truck\nDump Truck\nHeavy Truck\nConcrete Mixer\nService Van", "insert_after": "company"},
            {"fieldname": "custom_assigned_project", "label": "Assigned Project", "fieldtype": "Link",
             "options": "Project", "insert_after": "custom_fleet_category"},
            {"fieldname": "custom_assigned_cost_center", "label": "Fleet Cost Center", "fieldtype": "Link",
             "options": "Cost Center", "insert_after": "custom_assigned_project"},
            {"fieldname": "custom_registration_expiry", "label": "Registration Expiry", "fieldtype": "Date",
             "insert_after": "custom_assigned_cost_center"},
            {"fieldname": "custom_next_service_odometer", "label": "Next Service Odometer", "fieldtype": "Int",
             "insert_after": "custom_registration_expiry"},
            {"fieldname": "custom_operating_status", "label": "Operating Status", "fieldtype": "Select",
             "options": "\nAvailable\nAssigned\nMaintenance\nOut of Service", "insert_after": "custom_next_service_odometer"},
        ],
        "Vehicle Log": [
            {"fieldname": "custom_project", "label": "Project", "fieldtype": "Link",
             "options": "Project", "insert_after": "employee"},
            {"fieldname": "custom_cost_center", "label": "Cost Center", "fieldtype": "Link",
             "options": "Cost Center", "insert_after": "custom_project"},
            {"fieldname": "custom_route_from", "label": "Trip Origin", "fieldtype": "Data",
             "insert_after": "custom_cost_center"},
            {"fieldname": "custom_route_to", "label": "Trip Destination", "fieldtype": "Data",
             "insert_after": "custom_route_from"},
            {"fieldname": "custom_trip_purpose", "label": "Trip Purpose", "fieldtype": "Small Text",
             "insert_after": "custom_route_to"},
            {"fieldname": "custom_trip_distance_km", "label": "Trip Distance (km)", "fieldtype": "Int",
             "insert_after": "custom_trip_purpose"},
        ],
    }
    for dt, fs in custom_fields.items():
        for f in fs:
            old = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": f["fieldname"]},
                                      ["fieldtype", "options"], as_dict=True)
            if old and (old.fieldtype != f["fieldtype"] or
                        (f.get("options") and old.options != f["options"])):
                raise RuntimeError(f"Existing Custom Field conflicts: {dt}.{f['fieldname']}")
    create_custom_fields(custom_fields, update=False)
    frappe.db.commit()


def ensure_fleet_accounts(d):
    company = d["company"]
    group = frappe.db.get_value("Account", {
        "company": company, "account_name": "Construction Site Overheads", "is_group": 1}, "name")
    if not group:
        raise RuntimeError("Missing contractor expense group for Fleet: " + company)
    for n, label in (
        (529020, "Fleet Fuel and Lubricants"),
        (529021, "Fleet Service and Repairs"),
        (529022, "Fleet Insurance"),
        (529023, "Fleet Registration and Permits"),
        (529024, "Fleet Tolls and Transportation"),
    ):
        code = str(n)
        collision = frappe.db.get_value("Account", {
            "company": company, "account_number": code}, "account_name")
        if collision and collision != label:
            raise RuntimeError(f"Account number collision {code}: {collision}")
        account = ensure("Account", {"company": company, "account_name": label}, {
            "company": company, "account_name": label,
            "account_number": code, "parent_account": group,
            "is_group": 0, "account_type": "Indirect Expense",
        })
        doc = frappe.get_doc("Account", account)
        if doc.parent_account != group or str(doc.account_number) != code:
            raise RuntimeError(f"Fleet account mismatch {company}/{label}")


def ensure_fleet_drivers(d):
    ids = []
    for i, (first, last) in enumerate(FLEET_DRIVERS[d["abbr"]], start=1):
        employee_number = f"{d['abbr']}-DRV-{i:03d}"
        em = ensure("Employee", {"employee_number": employee_number}, {
            "employee_number": employee_number, "naming_series": "HR-EMP-",
            "first_name": first, "last_name": last, "gender": "Male", "designation": "Driver",
            "company": d["company"], "date_of_birth": date(1983 + i * 2, 3 + i, 8 + i),
            "date_of_joining": date(2023, i + 3, 1), "status": "Active",
            "create_user_permission": 0, "create_user_automatically": 0,
        })
        if frappe.db.get_value("Employee", em, "company") != d["company"]:
            raise RuntimeError("Driver from wrong company: " + em)
        ids.append(em)
    return ids


def fleet_setup(d):
    verify_fleet_dependencies()
    company, abbr = d["company"], d["abbr"]
    ensure_fleet_accounts(d)
    ensure("Designation", {"designation_name": "Driver"}, {"designation_name": "Driver"})
    drivers = ensure_fleet_drivers(d)
    fuel_supplier = FLEET_FUEL_SUPPLIERS[abbr]
    ensure("Supplier", {"supplier_name": fuel_supplier}, {
        "supplier_name": fuel_supplier, "supplier_type": "Company",
        "supplier_group": "Construction Material Suppliers",
    })
    supplier_name = frappe.db.get_value("Supplier", {"supplier_name": fuel_supplier}, "name")
    for service, _, _ in FLEET_CATEGORIES:
        ensure("Vehicle Service Item", {"service_item": service}, {"service_item": service})

    for i, (make, model, category, fuel_type, start_km, value, town, wheels) in enumerate(
        FLEET_CATALOG[abbr], start=1
    ):
        # Internal fleet ID used in License Plate field, NOT a governmental plate number.
        plate = f"{abbr}-FLT-{i:03d}"
        project_title, district, _ = d["projects"][(i - 1) % len(d["projects"])]
        project = frappe.db.get_value("Project", {"company": company, "project_name": project_title}, "name")
        if not project:
            raise RuntimeError("Missing fleet project: " + project_title)
        cc = frappe.db.get_value("Project", project, "cost_center")
        if not cc or frappe.db.get_value("Cost Center", cc, "company") != company:
            raise RuntimeError("Missing or incorrect fleet cost center for " + project)
        driver = drivers[(i - 1) % len(drivers)]
        initial = {
            "doctype": "Vehicle", "license_plate": plate, "company": company,
            "make": make, "model": model, "last_odometer": start_km,
            "fuel_type": fuel_type, "uom": "Litre", "wheels": wheels,
            "acquisition_date": f"202{(i % 3) + 1}-06-10", "location": town,
            "vehicle_value": value, "employee": driver,
            # The following sample policy has no real insurance coverage.
            "insurance_company": "Sample Insurance Provider", "policy_no": f"SAMPLE-{abbr}-{i:03d}",
            "start_date": "2026-01-01", "end_date": "2026-12-31",
            "custom_fleet_category": category, "custom_assigned_project": project,
            "custom_assigned_cost_center": cc,
            "custom_registration_expiry": "2027-01-31",
            "custom_next_service_odometer": start_km + 10000,
            "custom_operating_status": "Assigned",
        }
        vehicle_name = ensure("Vehicle", {"license_plate": plate}, initial)
        old_vehicle = frappe.get_doc("Vehicle", vehicle_name)
        if old_vehicle.company != company or old_vehicle.employee != driver:
            raise RuntimeError(f"Vehicle identity mismatch: {plate}")
        if old_vehicle.custom_assigned_project != project:
            raise RuntimeError(f"Vehicle assigned to unexpected project: {plate}")

        for j, day in enumerate(("2026-09-15", "2026-10-15"), start=1):
            exists_name = frappe.db.get_value("Vehicle Log", {"license_plate": plate, "date": day}, "name")
            if exists_name:
                log = frappe.get_doc("Vehicle Log", exists_name)
                if log.docstatus == 0:
                    log.submit()
                if log.employee != driver or log.custom_project != project:
                    raise RuntimeError("Vehicle Log relationship mismatch: " + exists_name)
                EXISTING["Vehicle Log"] += 1
                continue

            previous_km = int(frappe.db.get_value("Vehicle", plate, "last_odometer") or 0)
            increment = 360 + i * 25 + j * 40
            fuel_qty = 35 + i * 6 + j * 3
            values = {
                "doctype": "Vehicle Log", "naming_series": "HR-VLOG-.YYYY.-",
                "license_plate": plate, "employee": driver, "date": day,
                "last_odometer": previous_km, "odometer": previous_km + increment,
                "fuel_qty": fuel_qty, "price": FLEET_FUEL_PRICE[abbr],
                "supplier": supplier_name, "invoice": f"SAMPLE-FUEL-{abbr}-{i:03d}-{j}",
                "custom_project": project, "custom_cost_center": cc,
                "custom_route_from": town, "custom_route_to": district,
                "custom_trip_purpose": "Materials transport and scheduled project delivery",
                "custom_trip_distance_km": increment,
                "service_detail": [],
            }
            if j == 2:
                service_item, service_type, frequency = FLEET_CATEGORIES[(i - 1) % len(FLEET_CATEGORIES)]
                values["service_detail"].append({
                    "service_item": service_item, "type": service_type,
                    "frequency": frequency, "expense_amount": FLEET_SERVICE_COST[abbr],
                })
            log = frappe.get_doc(values)
            log.insert(ignore_permissions=True)
            log.submit()
            CREATED["Vehicle Log"] += 1
        frappe.db.commit()
    print(f"FLEET READY: {abbr} vehicles=4 drivers=3 logs=8", flush=True)


def fleet_audit():
    result = {"companies": {}, "errors": []}
    for d in DATA:
        company, abbr = d["company"], d["abbr"]
        vehicles = frappe.get_all("Vehicle", filters={"company": company},
                                  fields=["name", "employee", "custom_assigned_project", "custom_assigned_cost_center"])
        if len(vehicles) < 4:
            result["errors"].append(f"{abbr}: less than 4 vehicles")
        logs = 0
        for vehicle in vehicles:
            emp_company = frappe.db.get_value("Employee", vehicle.employee, "company")
            proj_company = frappe.db.get_value("Project", vehicle.custom_assigned_project, "company")
            cc_company = frappe.db.get_value("Cost Center", vehicle.custom_assigned_cost_center, "company")
            if not (emp_company == proj_company == cc_company == company):
                result["errors"].append(f"{abbr}: cross-company fleet link on {vehicle.name}")
            logs += frappe.db.count("Vehicle Log", {"license_plate": vehicle.name, "docstatus": 1})
        if logs < 8:
            result["errors"].append(f"{abbr}: less than 8 submitted Vehicle Logs")
        result["companies"][abbr] = {"vehicles": len(vehicles), "submitted_logs": logs,
                                     "drivers": frappe.db.count("Employee", {"company": company, "designation": "Driver"}),
                                     "fuel_account": frappe.db.get_value("Account", {"company": company, "account_number": "529020"}, "name")}
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "fleet", "audit"), default="all")
    args = parser.parse_args()
    frappe.init(site=SITE, sites_path=".")
    frappe.connect()
    frappe.set_user("Administrator")
    try:
        verify_site()
        if args.phase == "all":
            fixtures()
            for d in DATA:
                company_setup(d)
                construction_coa(d)
                number_accounts(d)
                print(f"COA READY: {d['company']}", flush=True)
            master_groups()
            for d in DATA:
                company_masters(d)
            for d in DATA:
                transaction_samples(d)
        if args.phase in ("all", "fleet"):
            # Safe resume when the v1 base seed was already run.
            for d in DATA:
                if not frappe.db.exists("Company", d["company"]) or not frappe.db.exists("Project", {"company": d["company"]}):
                    raise RuntimeError("Missing base multicompany/project records; use --phase all first")
            verify_fleet_dependencies()
            setup_fleet_fields()
            for d in DATA:
                fleet_setup(d)
        if args.phase != "audit":
            frappe.db.set_single_value("Global Defaults", "default_company", "Al Furqan Contracting")
            frappe.db.set_default("company", "Al Furqan Contracting")
            frappe.db.set_default("currency", "KWD")
            frappe.db.set_default("fiscal_year", "2026")
            for app in ("frappe", "erpnext", "hrms"):
                if not frappe.db.exists("Installed Application", {"app_name": app}):
                    raise RuntimeError("Missing installed app in setup table: " + app)
                frappe.db.set_value("Installed Application", {"app_name": app}, "is_setup_complete", 1)
            frappe.db.set_single_value("System Settings", "setup_complete", 1)
            frappe.db.commit()
            frappe.clear_cache()
        report = audit()
        flt = fleet_audit()
        print(json.dumps({"created": dict(CREATED), "existing": dict(EXISTING), "base_audit": report, "fleet_audit": flt}, indent=2, ensure_ascii=False), flush=True)
        if report["errors"] or flt["errors"]:
            raise RuntimeError("AUDIT FAILED; do not treat deployment as complete")
        print("CLEAN_MULTICOMPANY_FLEET_READY", flush=True)
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
